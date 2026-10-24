"""روت‌های دستیار جلسه زنده.

جریان: ساخت نشست ← ارسال تکه ← رونویسی ← آستانه ← پل AMP.
قاعده طلایی: user_id فقط از توکن. هر کاربر فقط نشست‌های خودش را می‌بیند.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    SCOPE_MEETING_READ, SCOPE_MEETING_WRITE, Principal, require_scope,
)
from app.db.live_models import (
    LiveAgent, LiveChunk, LiveSegment, LiveSession, LiveSessionAgent,
)
from app.db.session import get_db
from app.services import asr_sina, live_meeting

router = APIRouter(prefix="/v1/live", tags=["live-meeting"])

MAX_CHUNK_BYTES = 25 * 1024 * 1024  # ۲۵ مگابایت. تکه ۳۰ ثانیه حدود ۱۰۰ کیلوبایت است.


def _own(db: Session, uid, session_id: str) -> LiveSession:
    """نشست را با قید مالکیت می‌خواند. نشست غریبه ۴۰۴ می‌گیرد، نه ۴۰۳."""
    s = db.execute(select(LiveSession).where(
        LiveSession.id == session_id, LiveSession.user_id == uid)).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "نشست پیدا نشد")
    return s


@router.post("/sessions")
def create_session(body: dict,
                   p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                   db: Session = Depends(get_db)):
    # ایجنت‌های انتخاب‌شده از دفترچه. هر شناسه باید مال خود کاربر باشد،
    # وگرنه کاربر می‌توانست با حدس شناسه، توکن ایجنت غریبه را در جلسه بگذارد.
    ids = [str(x) for x in (body.get("agent_ids") or []) if x]
    picked: list[LiveAgent] = []
    if ids:
        picked = list(db.execute(select(LiveAgent).where(
            LiveAgent.user_id == p.user_id,
            LiveAgent.id.in_(ids),
            LiveAgent.archived.is_(False))).scalars().all())
        if len(picked) != len(set(ids)):
            raise HTTPException(404, "یکی از ایجنت‌ها پیدا نشد")

    s = LiveSession(
        user_id=p.user_id,
        title=(body.get("title") or None),
        diarize=bool(body.get("diarize", False)),
        word_threshold=int(body.get("word_threshold", 400)),
        time_threshold_s=int(body.get("time_threshold_s", 90)),
        silence_threshold_s=int(body.get("silence_threshold_s", 6)),
        min_words_to_send=int(body.get("min_words_to_send", 60)),
    )
    db.add(s)
    db.flush()
    # ترتیب `in_` تضمینی نیست، پس ترتیب انتخاب کاربر را دستی می‌گذاریم.
    order = {aid: i for i, aid in enumerate(ids)}
    for ag in sorted(picked, key=lambda a: order.get(str(a.id), 0)):
        db.add(LiveSessionAgent(session_id=s.id, agent_id=ag.id))
    db.commit()
    db.refresh(s)
    # پیام شروع جلسه: بدون آن ایجنت تا اولین آستانه بی خبر می ماند و کاربر
    # هم نمی فهمد اتصال برقرار شده یا نه. شکست این پیام جلسه را نمی بندد.
    start_note = None
    if picked:
        try:
            start_note = live_meeting.notify_meeting_started(db, s)
        except Exception as e:  # noqa: BLE001
            start_note = {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"ok": True, "session_id": str(s.id), "started_at": s.started_at.isoformat(),
            "start_note": start_note,
            "thresholds": {"words": s.word_threshold, "time_s": s.time_threshold_s,
                           "silence_s": s.silence_threshold_s,
                           "min_words": s.min_words_to_send},
            "agents": [{"agent_id": str(a.id), "name": a.name} for a in picked],
            "agent_count": len(picked)}


@router.post("/sessions/{session_id}/chunk")
async def push_chunk(session_id: str,
                     seq: int = Form(...),
                     start_s: float = Form(0),
                     end_s: float = Form(0),
                     silence: bool = Form(False),
                     file: UploadFile = File(...),
                     p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                     db: Session = Depends(get_db)):
    """ارسال یک تکه صدا. رونویسی می‌شود و اگر آستانه رد شد، به ایجنت می‌رود."""
    s = _own(db, p.user_id, session_id)
    if s.status != "recording":
        raise HTTPException(409, "نشست در حال ضبط نیست")

    audio = await file.read()
    if not audio:
        raise HTTPException(422, "فایل خالی است")
    if len(audio) > MAX_CHUNK_BYTES:
        raise HTTPException(413, "تکه بیش از ۲۵ مگابایت")

    # تکه تکراری: همان seq قبلا ثبت شده. دوباره رونویسی نمی‌کنیم.
    dup = db.execute(select(LiveChunk).where(
        LiveChunk.session_id == s.id, LiveChunk.seq == seq)).scalar_one_or_none()
    if dup is not None and dup.status == "done":
        return {"ok": True, "duplicate": True, "seq": seq, "text": dup.text,
                "words": dup.words, "session_words": s.total_words}

    chunk = dup or LiveChunk(session_id=s.id, seq=seq)
    chunk.start_s = start_s
    chunk.end_s = end_s
    chunk.bytes = len(audio)
    chunk.silence = silence
    chunk.status = "running"
    chunk.error = None
    if dup is None:
        db.add(chunk)
    db.commit()

    try:
        res = asr_sina.transcribe(
            audio,
            filename=file.filename or f"chunk_{seq}.webm",
            content_type=file.content_type or "audio/webm",
            diarize=s.diarize,
        )
    except asr_sina.SinaError as e:
        chunk.status = "error"
        chunk.error = str(e)[:400]
        db.commit()
        raise HTTPException(502, f"سرویس صوت: {e}") from e
    except Exception as e:  # noqa: BLE001
        chunk.status = "error"
        chunk.error = f"{type(e).__name__}: {str(e)[:300]}"
        db.commit()
        raise HTTPException(502, "سرویس صوت پاسخ نداد") from e

    chunk.status = "done"
    chunk.text = res["text"]
    chunk.words = res["word_count"]
    s.total_words = (s.total_words or 0) + res["word_count"]
    db.commit()

    # آستانه
    trigger = live_meeting.should_send(db, s, last_chunk_silence=bool(silence))
    sent = None
    if trigger:
        sent = live_meeting.flush_to_agent(db, s, trigger)

    db.refresh(s)
    return {"ok": True, "seq": seq, "text": res["text"], "words": res["word_count"],
            "session_words": s.total_words, "trigger": trigger, "sent": sent}


@router.get("/sessions/{session_id}")
def get_session(session_id: str,
                p: Principal = Depends(require_scope(SCOPE_MEETING_READ)),
                db: Session = Depends(get_db)):
    """وضعیت زنده: متن کامل، شمارنده، بازه‌های ارسالی. برای خواندن ایجنت."""
    s = _own(db, p.user_id, session_id)
    text = live_meeting.session_transcript(db, s.id)
    pending, from_seq, to_seq = live_meeting.pending_text(db, s)
    segs = db.execute(select(LiveSegment).where(
        LiveSegment.session_id == s.id).order_by(LiveSegment.id)).scalars().all()
    return {
        "ok": True, "session_id": str(s.id), "title": s.title, "status": s.status,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "total_words": s.total_words,
        "last_sent_seq": s.last_sent_seq,
        "pending_words": live_meeting.count_words(pending),
        # وقتی متنی معلق نیست، بازه معنا ندارد. صفر نشان نمی‌دهیم چون صفر خودش شماره تکه معتبر است.
        "pending_from_seq": from_seq if pending else None,
        "pending_to_seq": to_seq if pending else None,
        "agent_attached": bool(s.agent_token),
        # گیرنده‌های فعال و عقب‌مانده‌ترین نشانگر. کاربر باید ببیند چه کسی
        # در جلسه هست و چقدر متن برای هر کدام معلق مانده.
        "agents": [{"agent_id": str(r.agent_id) if r.agent_id else None,
                    "name": r.name,
                    "words_since": live_meeting.count_words(
                        live_meeting.pending_text_since(db, s, r.since_seq)[0]),
                    "amp_ready": bool(r.amp_session_id),
                    "legacy": r.legacy} for r in live_meeting.recipients(db, s)],
        "thresholds": {"words": s.word_threshold, "time_s": s.time_threshold_s,
                       "silence_s": s.silence_threshold_s},
        "transcript": text,
        "segments": [{"id": x.id, "from_seq": x.from_seq, "to_seq": x.to_seq,
                      "from_s": float(x.from_s), "to_s": float(x.to_s),
                      "words": x.words, "trigger": x.trigger,
                      "sent": x.sent_to_agent, "error": x.send_error,
                      "reply": x.agent_reply, "amp_msg_id": x.amp_msg_id,
                      "at": x.created_at.isoformat()} for x in segs],
    }


@router.get("/sessions/{session_id}/transcript")
def get_transcript(session_id: str, since_seq: int = 0,
                   p: Principal = Depends(require_scope(SCOPE_MEETING_READ)),
                   db: Session = Depends(get_db)):
    """متن از تکه شماره N به بعد. ابزار اصلی ایجنت برای خواندن زنده."""
    s = _own(db, p.user_id, session_id)
    # شامل خود since_seq. با > ، تکه صفر همیشه حذف می‌شد و اولین تکه هر جلسه گم می‌شد.
    rows = db.execute(select(LiveChunk).where(
        LiveChunk.session_id == s.id, LiveChunk.seq >= since_seq,
        LiveChunk.status == "done").order_by(LiveChunk.seq)).scalars().all()
    last = rows[-1].seq if rows else since_seq - 1
    return {"ok": True, "session_id": str(s.id),
            "chunks": [{"seq": c.seq, "start_s": float(c.start_s), "end_s": float(c.end_s),
                        "text": c.text, "words": c.words} for c in rows],
            "last_seq": last,
            # برای نظرسنجی بعدی همین را به since_seq بده تا تکه تکراری نگیری.
            "next_seq": last + 1,
            "total_words": s.total_words}


@router.post("/sessions/{session_id}/test")
def test_session(session_id: str,
                 p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                 db: Session = Depends(get_db)):
    """آزمون سریع مسیر ارسال، بدون نیاز به صحبت کردن.

    قبلا برای سنجیدن اتصال، کاربر باید نیم دقیقه حرف می زد تا آستانه رد شود.
    این روت همان مسیر واقعی را با یک متن کوتاه می آزماید.
    """
    s = _own(db, p.user_id, session_id)
    res = live_meeting.send_test_message(db, s)
    return res


@router.post("/sessions/{session_id}/agents")
def add_session_agents(session_id: str, body: dict,
                       p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                       db: Session = Depends(get_db)):
    """افزودن ایجنت به جلسه در حال اجرا.

    ایجنت تازه‌پیوسته کل متن جلسه را یک بار می‌گیرد، چون نشانگرش منفی یک
    است. این رفتار درست است: مشاور باید بداند تا این لحظه چه گفته شده.
    """
    s = _own(db, p.user_id, session_id)
    ids = [str(x) for x in (body.get("agent_ids") or []) if x]
    if not ids:
        raise HTTPException(422, "هیچ ایجنت انتخاب نشده")
    picked = list(db.execute(select(LiveAgent).where(
        LiveAgent.user_id == p.user_id,
        LiveAgent.id.in_(ids),
        LiveAgent.archived.is_(False))).scalars().all())
    if len(picked) != len(set(ids)):
        raise HTTPException(404, "یکی از ایجنت‌ها پیدا نشد")
    have = set(db.execute(select(LiveSessionAgent.agent_id).where(
        LiveSessionAgent.session_id == s.id,
        LiveSessionAgent.agent_id.in_([a.id for a in picked]))).scalars().all())
    added = []
    for ag in picked:
        if ag.id in have:
            continue
        db.add(LiveSessionAgent(session_id=s.id, agent_id=ag.id))
        added.append({"agent_id": str(ag.id), "name": ag.name})
    db.commit()
    return {"ok": True, "added": added, "added_count": len(added),
            "skipped": len(picked) - len(added)}


@router.delete("/sessions/{session_id}/agents/{agent_id}")
def remove_session_agent(session_id: str, agent_id: str,
                         p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                         db: Session = Depends(get_db)):
    """حذف ایجنت از این جلسه. خود ایجنت و تاریخچه‌اش دست‌نخورده می‌ماند."""
    s = _own(db, p.user_id, session_id)
    row = db.execute(select(LiveSessionAgent).where(
        LiveSessionAgent.session_id == s.id,
        LiveSessionAgent.agent_id == agent_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "این ایجنت در این جلسه نیست")
    db.delete(row)
    db.commit()
    return {"ok": True, "removed": agent_id}


@router.post("/sessions/{session_id}/flush")
def flush(session_id: str,
          p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
          db: Session = Depends(get_db)):
    """ارسال دستی متن معلق به ایجنت. دکمه «الان نظر بده»."""
    s = _own(db, p.user_id, session_id)
    return live_meeting.flush_to_agent(db, s, "manual")


@router.post("/sessions/{session_id}/sync-replies")
def sync_replies(session_id: str,
                 p: Principal = Depends(require_scope(SCOPE_MEETING_READ)),
                 db: Session = Depends(get_db)):
    """پاسخ‌های تازه ایجنت را از کانال AMP می‌کشد و برمی‌گرداند."""
    s = _own(db, p.user_id, session_id)
    n = live_meeting.sync_replies(db, s)
    rows = db.execute(select(LiveSegment).where(
        LiveSegment.session_id == s.id,
        LiveSegment.agent_reply.isnot(None)).order_by(LiveSegment.id)).scalars().all()
    return {"ok": True, "updated": n, "replies": [
        {"segment_id": x.id, "words": x.words, "trigger": x.trigger,
         "agent_id": str(x.agent_id) if x.agent_id else None,
         "agent_name": x.agent_name,
         "reply": x.agent_reply} for x in rows]}


@router.post("/sessions/{session_id}/stop")
def stop_session(session_id: str,
                 p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                 db: Session = Depends(get_db)):
    s = _own(db, p.user_id, session_id)
    s.status = "stopped"
    s.ended_at = datetime.now(timezone.utc)
    db.commit()
    text = live_meeting.session_transcript(db, s.id)
    return {"ok": True, "session_id": str(s.id), "status": s.status,
            "total_words": s.total_words, "transcript": text}


# ---------- دفترچه ایجنت‌ها ----------
# قاعده: توکن هرگز در پاسخ برنمی‌گردد. فقط چهار کاراکتر آخر برای بازشناسی.

def _mask(token: str) -> str:
    t = (token or "").strip()
    if len(t) <= 4:
        return "••••"
    return "••••" + t[-4:]


def _agent_out(a: LiveAgent) -> dict:
    return {"agent_id": str(a.id), "name": a.name, "note": a.note,
            "token_hint": _mask(a.token), "token_ok": a.token_ok,
            "last_error": a.last_error,
            "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
            "created_at": a.created_at.isoformat()}


def _own_agent(db: Session, uid, agent_id: str) -> LiveAgent:
    a = db.execute(select(LiveAgent).where(
        LiveAgent.id == agent_id, LiveAgent.user_id == uid)).scalar_one_or_none()
    if a is None:
        raise HTTPException(404, "ایجنت پیدا نشد")
    return a


@router.get("/agents")
def list_agents(include_archived: bool = False,
                p: Principal = Depends(require_scope(SCOPE_MEETING_READ)),
                db: Session = Depends(get_db)):
    """دفترچه ایجنت‌های کاربر. توکن خام هرگز برنمی‌گردد."""
    q = select(LiveAgent).where(LiveAgent.user_id == p.user_id)
    if not include_archived:
        q = q.where(LiveAgent.archived.is_(False))
    rows = db.execute(q.order_by(LiveAgent.created_at)).scalars().all()
    return {"ok": True, "agents": [_agent_out(a) for a in rows]}


@router.post("/agents")
def create_agent(body: dict,
                 p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                 db: Session = Depends(get_db)):
    """ثبت یک ایجنت در دفترچه. توکن یک بار داده می‌شود و ذخیره می‌ماند."""
    name = (body.get("name") or "").strip()
    token = (body.get("token") or "").strip()
    if not name:
        raise HTTPException(422, "نام ایجنت لازم است")
    if not token:
        raise HTTPException(422, "توکن ایجنت لازم است")
    if not token.startswith("amp_"):
        raise HTTPException(422, "توکن باید با amp_ شروع شود")

    dup = db.execute(select(LiveAgent).where(
        LiveAgent.user_id == p.user_id,
        func.lower(LiveAgent.name) == name.lower(),
        LiveAgent.archived.is_(False))).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(409, "ایجنت با این نام از قبل هست")

    a = LiveAgent(user_id=p.user_id, name=name, token=token,
                  note=(body.get("note") or None))
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"ok": True, "agent": _agent_out(a)}


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: str, body: dict,
                 p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                 db: Session = Depends(get_db)):
    """ویرایش نام، یادداشت یا توکن. توکن خالی یعنی دست نزن."""
    a = _own_agent(db, p.user_id, agent_id)
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(422, "نام ایجنت لازم است")
        clash = db.execute(select(LiveAgent).where(
            LiveAgent.user_id == p.user_id,
            LiveAgent.id != a.id,
            LiveAgent.archived.is_(False),
            func.lower(LiveAgent.name) == name.lower())).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(409, "نام تکراری است")
        a.name = name
    if body.get("token"):
        token = str(body["token"]).strip()
        if not token.startswith("amp_"):
            raise HTTPException(422, "توکن باید با amp_ شروع شود")
        a.token = token
        # توکن عوض شد، پس آزمون قبلی بی‌اعتبار است.
        a.token_ok = None
        a.last_error = None
    if "note" in body:
        a.note = (body.get("note") or None)
    db.commit()
    db.refresh(a)
    return {"ok": True, "agent": _agent_out(a)}


@router.post("/agents/{agent_id}/test")
def test_agent(agent_id: str,
               p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
               db: Session = Depends(get_db)):
    """توکن را می‌آزماید: یک نشست AMP باز می‌کند.

    بدون این آزمون، کاربر تا وسط جلسه نمی‌فهمید توکن غلط است.
    """
    a = _own_agent(db, p.user_id, agent_id)
    res = live_meeting.probe_agent_token(a.token, a.name)
    a.token_ok = bool(res.get("ok"))
    a.last_error = None if res.get("ok") else str(res.get("error"))[:300]
    db.commit()
    db.refresh(a)
    return {"ok": bool(res.get("ok")), "error": a.last_error, "agent": _agent_out(a)}


@router.delete("/agents/{agent_id}")
def archive_agent(agent_id: str,
                  p: Principal = Depends(require_scope(SCOPE_MEETING_WRITE)),
                  db: Session = Depends(get_db)):
    """بایگانی ایجنت. حذف واقعی نه، چون تاریخچه بازه‌ها به آن اشاره دارد."""
    a = _own_agent(db, p.user_id, agent_id)
    a.archived = True
    db.commit()
    return {"ok": True, "agent_id": str(a.id), "archived": True}


@router.get("/sessions")
def list_sessions(limit: int = 30,
                  p: Principal = Depends(require_scope(SCOPE_MEETING_READ)),
                  db: Session = Depends(get_db)):
    rows = db.execute(select(LiveSession).where(
        LiveSession.user_id == p.user_id)
        .order_by(LiveSession.started_at.desc()).limit(min(limit, 100))).scalars().all()
    return {"ok": True, "sessions": [
        {"session_id": str(s.id), "title": s.title, "status": s.status,
         "started_at": s.started_at.isoformat(),
         "ended_at": s.ended_at.isoformat() if s.ended_at else None,
         "total_words": s.total_words} for s in rows]}


@router.get("/health")
def live_health():
    """سلامت ماژول و دسترسی به سرویس صوت."""
    try:
        h = asr_sina.health()
        return {"ok": True, "asr": "up", "model": h.get("model"),
                "workers": h.get("workers"), "queued": h.get("jobs_queued")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "asr": "down", "error": f"{type(e).__name__}: {str(e)[:200]}"}
