"""منطق دستیار جلسه زنده: آستانه، تجمیع متن، پل AMP.

قاعده طلایی: user_id از توکن می‌آید، نه از ورودی. هر نشست فقط برای صاحبش.
آستانه: هر کدام از کلمه/زمان/سکوت/دستی اول رسید، ارسال انجام می‌شود.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.live_models import (
    LiveAgent, LiveChunk, LiveSegment, LiveSession, LiveSessionAgent,
)


# ---------- متن ----------

def session_transcript(db: Session, session_id) -> str:
    """متن کامل نشست از تکه‌های موفق، به ترتیب."""
    rows = db.execute(
        select(LiveChunk.text).where(
            LiveChunk.session_id == session_id,
            LiveChunk.status == "done",
            LiveChunk.text.isnot(None),
        ).order_by(LiveChunk.seq)).scalars().all()
    return " ".join(t.strip() for t in rows if t and t.strip())


def pending_text_since(db: Session, session: LiveSession, since_seq: int) -> tuple[str, int, int]:
    """متن تکه‌های موفق بعد از یک نشانگر. برمی‌گرداند (متن, از_seq, تا_seq).

    نشانگر منفی یک یعنی هیچ‌چیز ارسال نشده، پس شرط > درست است و تکه شماره
    صفر را هم شامل می‌شود. اگر نشانگر صفر بود، تکه صفر گم می‌شد.
    """
    rows = db.execute(
        select(LiveChunk.seq, LiveChunk.text).where(
            LiveChunk.session_id == session.id,
            LiveChunk.seq > since_seq,
            LiveChunk.status == "done",
            LiveChunk.text.isnot(None),
        ).order_by(LiveChunk.seq)).all()
    if not rows:
        return "", since_seq, since_seq
    text = " ".join((t or "").strip() for _, t in rows if t and t.strip())
    return text.strip(), rows[0][0], rows[-1][0]


def pending_text(db: Session, session: LiveSession) -> tuple[str, int, int]:
    """متن معلق نسبت به نشانگر خود نشست. برای گزارش وضعیت."""
    return pending_text_since(db, session, session.last_sent_seq)


def count_words(text: str) -> int:
    return len([w for w in (text or "").split() if w.strip()])


# ---------- گیرندگان ----------

class Recipient:
    """یک گیرنده ارسال در این نشست: یک ایجنت با نشانگر مستقل خودش.

    نشانگر باید per-ایجنت باشد. اگر دو ایجنت داشته باشیم و یکی خطا بدهد،
    نشانگر مشترک یا جلو می‌رود و متن برای آن یکی گم می‌شود، یا جلو نمی‌رود
    و ایجنت سالم متن تکراری می‌گیرد. پس هر پیوند نشانگر خودش را دارد.
    """
    __slots__ = ("agent_id", "name", "token", "amp_session_id", "since_seq",
                 "last_sent_at", "pairing", "legacy")

    def __init__(self, agent_id, name, token, amp_session_id, since_seq,
                 last_sent_at=None, pairing=None, legacy=False):
        self.agent_id = agent_id
        self.name = name
        self.token = token
        self.amp_session_id = amp_session_id
        self.since_seq = since_seq
        self.last_sent_at = last_sent_at
        self.pairing = pairing
        self.legacy = legacy

    def save_marker(self, db: Session, session: LiveSession, to_seq: int) -> None:
        """نشانگر را بعد از ارسال موفق جلو می‌برد. فقط همین ایجنت."""
        now = datetime.now(timezone.utc)
        self.since_seq = to_seq
        self.last_sent_at = now
        if self.legacy:
            session.last_sent_seq = to_seq
            session.last_sent_at = now
            session.amp_session_id = self.amp_session_id
        elif self.pairing is not None:
            self.pairing.last_sent_seq = to_seq
            self.pairing.last_sent_at = now
            self.pairing.amp_session_id = self.amp_session_id

    def persist_amp_session(self, db: Session, session: LiveSession) -> None:
        """نشست AMP را روی درست‌ترین جا ذخیره می‌کند."""
        if self.legacy:
            session.amp_session_id = self.amp_session_id
        elif self.pairing is not None:
            self.pairing.amp_session_id = self.amp_session_id
        db.commit()


def recipients(db: Session, session: LiveSession) -> list[Recipient]:
    """گیرندگان این نشست: ایجنت‌های انتخاب‌شده، به‌ترتیب پیوستن.

    اگر نشست هنوز ایجنت دفترچه‌ای ندارد ولی توکن قدیمی روی خودش دارد،
    مسیر تک‌ایجنت قدیمی برگردانده می‌شود تا نشست‌های قبلی نشکنند.
    """
    rows = db.execute(
        select(LiveSessionAgent, LiveAgent)
        .join(LiveAgent, LiveAgent.id == LiveSessionAgent.agent_id)
        .where(LiveSessionAgent.session_id == session.id,
               LiveAgent.archived.is_(False))
        .order_by(LiveSessionAgent.joined_at)).all()
    out = [
        Recipient(
            agent_id=ag.id, name=ag.name, token=ag.token,
            amp_session_id=link.amp_session_id,
            since_seq=(-1 if link.last_sent_seq is None else link.last_sent_seq),
            last_sent_at=link.last_sent_at,
            pairing=link,
        ) for link, ag in rows
    ]
    if not out and session.agent_token:
        out.append(Recipient(
            agent_id=None, name=session.agent_label or "دستیار جلسه",
            token=session.agent_token, amp_session_id=session.amp_session_id,
            since_seq=(-1 if session.last_sent_seq is None else session.last_sent_seq),
            last_sent_at=session.last_sent_at, legacy=True,
        ))
    return out


def oldest_marker(recs: list[Recipient]) -> int:
    """عقب‌مانده‌ترین نشانگر. آستانه باید بر مبنای همین سنجیده شود."""
    return min((r.since_seq for r in recs), default=-1)


# ---------- آستانه ----------

def should_send(db: Session, session: LiveSession, last_chunk_silence: bool = False) -> str | None:
    """آیا باید به ایجنت‌ها بفرستیم؟ اگر بله، دلیل را برمی‌گرداند."""
    recs = recipients(db, session)
    # بدون گیرنده، ارسال هیچ‌وقت موفق نمی‌شود. پس آستانه را بیخودی رد نمی‌کنیم
    # و بازه‌های شکست‌خورده انباشته نمی‌شوند.
    if not recs:
        return None

    text, _, _ = pending_text_since(db, session, oldest_marker(recs))
    if not text:
        return None
    words = count_words(text)
    if words < session.min_words_to_send:
        return None

    if words >= session.word_threshold:
        return "words"

    ref = min((r.last_sent_at for r in recs if r.last_sent_at), default=None)
    base = ref or session.started_at
    elapsed = (datetime.now(timezone.utc) - base).total_seconds()
    if elapsed >= session.time_threshold_s:
        return "time"

    if last_chunk_silence:
        # سکوت طولانی یعنی پایان یک موضوع. بهترین لحظه مشارکت.
        return "silence"

    return None


# ---------- پل AMP ----------

def _amp_url() -> str:
    return os.getenv("AMP_URL", "https://rudabeh-v2.hashpa.com/amp/mcp").strip()


def _mcp_url() -> str:
    """آدرس MCP خودمان که در peer نشست AMP معرفی می‌شود."""
    return os.getenv("BEHOOSH_MCP_URL", "https://behoosh.hashpa.com/mcp").strip()


def _amp_call(token: str, method: str, params: dict, session_id: str | None = None,
              timeout: float = 60.0) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": str(uuid.uuid4()),
                       "method": method, "params": params}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    r = httpx.post(_amp_url(), content=body, headers=headers, timeout=timeout)
    r.raise_for_status()
    raw = r.text
    # پاسخ streamable-http به شکل SSE می‌آید: خط data: را باید جدا کرد
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw[:500]}


def _amp_tool(token: str, name: str, args: dict, timeout: float = 60.0) -> dict:
    """یک ابزار AMP را صدا می‌زند و پوشش MCP را باز می‌کند.

    پاسخ ابزار داخل result.content[0].text به شکل رشته JSON می‌آید.
    اگر این پوشش باز نشود، خطای ابزار (ok=false) دیده نمی‌شود و
    ارسال شکست‌خورده موفق شمرده می‌شود. این باگ واقعی بود.
    """
    env = _amp_call(token, "tools/call", {"name": name, "arguments": args},
                    timeout=timeout)
    if "error" in env:
        return {"ok": False, "error": env["error"]}
    res = env.get("result") or {}
    if res.get("isError"):
        return {"ok": False, "error": res}
    content = res.get("content") or []
    if not content or not isinstance(content[0], dict):
        return {"ok": False, "error": "پاسخ خالی از AMP"}
    text = content[0].get("text")
    if text is None:
        return {"ok": False, "error": "متن پاسخ AMP نبود"}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": True, "raw": text[:500]}


def _friendly_amp_error(err) -> str:
    """خطای AMP را به پیام فارسی قابل فهم تبدیل می کند.

    خطای خام AMP برای کاربر بی معنی است. مهم ترین حالت: توکن سالم است
    ولی نشستی که به آن قفل شده بسته یا منقضی شده. آنجا کاربر باید از
    پنل توکن تازه بسازد، نه اینکه دنبال باگ بگردد.
    """
    code, msg = "", ""
    if isinstance(err, dict):
        code = str(err.get("code") or "")
        msg = str(err.get("message") or "")
    else:
        msg = str(err or "")
        for c in ("SESSION_CLOSED", "SESSION_MISMATCH", "TOKEN_UNBOUND", "MESSAGE_INVALID"):
            if c in msg:
                code = c
                break
    if code == "SESSION_CLOSED":
        return ("نشست این توکن در AMP بسته است. توکن سالم است ولی نشستش "
                "بسته یا منقضی شده. از پنل یک توکن تازه بساز.")
    if code == "SESSION_MISMATCH":
        return "این توکن به نشست دیگری قفل است. از پنل یک توکن تازه بساز."
    if code == "TOKEN_UNBOUND":
        return "این توکن قدیمی است و نشست ندارد. از پنل یک توکن تازه بساز."
    if code == "MESSAGE_INVALID":
        return f"آدرس MCP ما برای AMP قابل قبول نبود: {msg[:200]}"
    return (msg[:250] or "خطای نامشخص AMP")


def _open_amp_session(token: str, peer: dict, timeout: float = 25.0) -> dict:
    """نشست AMP را باز می‌کند، با تلاش دوباره روی خطای گذرای رزولور.

    گارد امنیتی سرور AMP پیش از باز کردن نشست، میزبان peer را با
    getaddrinfo حل می‌کند و اگر حل نشود کل نشست را رد می‌کند
    (MESSAGE_INVALID «peer host does not resolve»). رزولور آن سرور گاهی
    برای چند ثانیه از کار می‌افتد. یک تلاش دوباره با فاصله کوتاه همین
    نوسان گذرا را رد می‌کند و ارسال به ایجنت شکست نمی‌خورد.
    """
    transient = ("does not resolve", "name resolution", "No address associated")
    last: dict = {}
    for attempt in range(3):
        try:
            res = _amp_tool(token, "amp_open_session",
                            {"token": token, "peer": peer}, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        if res.get("ok"):
            return res
        last = res
        msg = str(res.get("error") or "")
        if not any(t in msg for t in transient):
            return res
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return last


def probe_agent_token(token: str, name: str = "") -> dict:
    """توکن ایجنت را می‌آزماید: یک نشست AMP باز می‌کند و نتیجه را برمی‌گرداند.

    بدون این آزمون، کاربر تا وسط جلسه نمی‌فهمید توکن غلط است. این تابع
    چیزی ذخیره نمی‌کند و فقط می‌گوید توکن زنده است یا نه.
    """
    if not token or not str(token).startswith("amp_"):
        return {"ok": False, "error": "توکن باید با amp_ شروع شود"}
    peer = {"name": (name or "behoosh-live"), "mcp_url": _mcp_url()}
    try:
        # تایم اوت کوتاه: آزمون توکن باید سریع جواب بدهد. توکن نامعتبر روی
        # AMP معلق می‌ماند و با ۶۰ ثانیه، کاربر پشت دکمه منتظر می‌ماند.
        res = _open_amp_session(token, peer, timeout=12.0)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:250]}"}
    if not res.get("ok"):
        return {"ok": False, "error": _friendly_amp_error(res.get("error"))}
    sid = res.get("session_id")
    if not sid:
        return {"ok": False, "error": "AMP بدون session_id پاسخ داد"}
    # نشست آزمون را نمی‌بندیم. توکن AMP به یک نشست قفل است و بستن آن،
    # همان توکن را برای ارسال واقعی وسط جلسه می‌کشد (خطای SESSION_CLOSED).
    return {"ok": True, "session_id": sid}


def ensure_amp_session(db: Session, session: LiveSession,
                       r: Recipient, timeout: float = 25.0) -> tuple[str | None, str | None]:
    """نشست AMP این ایجنت را می‌گیرد و ذخیره می‌کند.

    توکن AMP به یک نشست قفل است. فرستادن session_id خالی خطای
    SESSION_MISMATCH می‌دهد. پس اول باید نشست ساخته شود. هر ایجنت نشست
    خودش را دارد تا دو جلسه همزمان همدیگر را خراب نکنند.
    """
    if r.amp_session_id:
        return r.amp_session_id, None
    peer = {"name": r.name or "behoosh-live", "mcp_url": _mcp_url()}
    res = _open_amp_session(r.token, peer, timeout=timeout)
    if not res.get("ok"):
        return None, _friendly_amp_error(res.get("error"))
    sid = res.get("session_id")
    if not sid:
        return None, "AMP بدون session_id پاسخ داد"
    r.amp_session_id = sid
    r.persist_amp_session(db, session)
    return sid, None


def send_to_agent(db: Session, session: LiveSession, r: Recipient, text: str,
                  trigger: str, timeout: float = 60.0) -> tuple[bool, str | None, str | None]:
    """متن را به یک ایجنت از طریق AMP می‌فرستد.

    برمی‌گرداند (موفق, خطا, شناسه پیام). شناسه پیام لازم است چون پاسخ ایجنت
    با reply_to به همین شناسه برمی‌گردد و باید به بازه درست وصل شود.
    """
    if not r.token:
        return False, "توکن ایجنت برای این نشست تنظیم نشده", None
    label = r.name or "دستیار جلسه"
    env = _mcp_url()
    body = (
        f"[جلسه زنده — {label}]\n"
        f"شناسه جلسه: {session.id}\n"
        f"این جلسه برای کاربر {session.user_id} است. "
        f"برای خواندن متن تازه ابزار meeting_transcript(شناسه جلسه, since_seq) را صدا کن. "
        f"سرور MCP: {env}\n"
        f"دلیل ارسال: {trigger}\n"
        f"--- متن جلسه تا این لحظه ---\n{text}"
    )

    asid, err = ensure_amp_session(db, session, r, timeout=timeout)
    if not asid:
        return False, err, None

    msg_id = str(uuid.uuid4())

    def _send(sid: str) -> dict:
        return _amp_tool(r.token, "amp_send", {
            "token": r.token,
            "session_id": sid,
            "message": {
                "id": msg_id,
                "kind": "request",
                "topic": "meeting-live",
                "text": body,
            },
            "wait_for_response": False,
        }, timeout=timeout)

    try:
        res = _send(asid)
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:250]}", None

    # اگر نشست ذخیره‌شده دیگر معتبر نبود، یک بار نشست تازه می‌گیریم و دوباره می‌فرستیم.
    err_obj = res.get("error")
    code = err_obj.get("code") if isinstance(err_obj, dict) else None
    if not res.get("ok") and code in ("SESSION_MISMATCH", "SESSION_UNKNOWN", "SESSION_CLOSED"):
        r.amp_session_id = None
        r.persist_amp_session(db, session)
        asid, err = ensure_amp_session(db, session, r, timeout=timeout)
        if not asid:
            return False, err, None
        try:
            res = _send(asid)
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {str(e)[:250]}", None

    if not res.get("ok"):
        return False, _friendly_amp_error(res.get("error")), None
    return True, None, msg_id


def _mark_agent_used(db: Session, agent_id) -> None:
    """آخرین استفاده ایجنت را ثبت می‌کند. خطا اینجا مهم نیست."""
    if not agent_id:
        return
    ag = db.get(LiveAgent, agent_id)
    if ag is not None:
        ag.last_used_at = datetime.now(timezone.utc)


def sync_replies(db: Session, session: LiveSession) -> int:
    """پاسخ ایجنت‌ها را از کانال AMP می‌کشد و به بازه مربوطه می‌چسباند.

    ارسال غیرهمگام است، پس پاسخ بعدا می‌رسد. هر پاسخ با reply_to به شناسه
    پیام ما اشاره می‌کند. برای هر ایجنت یک بار تاریخچه خوانده می‌شود.
    تعداد پاسخ‌های تازه را برمی‌گرداند.
    """
    segs = db.execute(
        select(LiveSegment).where(
            LiveSegment.session_id == session.id,
            LiveSegment.sent_to_agent.is_(True),
            LiveSegment.agent_reply.is_(None),
            LiveSegment.amp_msg_id.isnot(None),
        )).scalars().all()
    if not segs:
        return 0

    groups: dict[object, list[LiveSegment]] = {}
    for seg in segs:
        groups.setdefault(seg.agent_id, []).append(seg)

    recs = {r.agent_id: r for r in recipients(db, session)}
    n = 0
    for aid, group in groups.items():
        r = recs.get(aid)
        # ایجنت بایگانی‌شده توکنش در دسترس نیست، پس تاریخچه‌اش خوانده نمی‌شود.
        if r is None or not r.amp_session_id:
            continue
        try:
            res = _amp_tool(r.token, "amp_history", {
                "token": r.token,
                "session_id": r.amp_session_id,
                "limit": 200,
            })
        except Exception:  # noqa: BLE001
            continue
        if not res.get("ok"):
            continue
        by_reply: dict[str, str] = {}
        for m in (res.get("messages") or []):
            if m.get("kind") == "response" and m.get("reply_to"):
                by_reply[str(m["reply_to"])] = (m.get("text") or "").strip()
        for seg in group:
            reply = by_reply.get(str(seg.amp_msg_id)) or ""
            if reply:
                seg.agent_reply = reply
                n += 1
    if n:
        db.commit()
    return n


def flush_to_agents(db: Session, session: LiveSession, trigger: str = "manual") -> dict:
    """متن معلق را به همه ایجنت‌های انتخاب‌شده می‌فرستد.

    به هر ایجنت فقط متنی می‌رود که خودش ندیده. پس ایجنت تازه‌پیوسته
    وسط جلسه، کل متن جلسه را یک بار می‌گیرد و ایجنت قدیمی فقط تازه‌ها را.
    """
    recs = recipients(db, session)
    if not recs:
        return {"ok": False, "reason": "هیچ ایجنت متصلی برای این نشست انتخاب نشده",
                "recipients": []}

    results: list[dict] = []
    any_sent = False
    any_text = False
    for r in recs:
        text, from_seq, to_seq = pending_text_since(db, session, r.since_seq)
        if not text:
            results.append({"agent_id": str(r.agent_id) if r.agent_id else None,
                            "agent_name": r.name, "ok": True, "skipped": True,
                            "words": 0})
            continue
        any_text = True
        words = count_words(text)
        ok, err, msg_id = send_to_agent(db, session, r, text, trigger)

        first = db.execute(select(LiveChunk.start_s).where(
            LiveChunk.session_id == session.id, LiveChunk.seq == from_seq)).scalar()
        last = db.execute(select(LiveChunk.end_s).where(
            LiveChunk.session_id == session.id, LiveChunk.seq == to_seq)).scalar()

        seg = LiveSegment(
            session_id=session.id, from_seq=from_seq, to_seq=to_seq,
            from_s=first or 0, to_s=last or 0, text=text, words=words,
            trigger=trigger, sent_to_agent=ok, send_error=err,
            amp_msg_id=msg_id, agent_id=r.agent_id, agent_name=r.name,
        )
        db.add(seg)

        # نشانگر فقط در صورت ارسال موفق جلو می‌رود. اگر ارسال شکست بخورد،
        # متن معلق می‌ماند تا در تلاش بعدی دوباره فرستاده شود، نه اینکه گم شود.
        if ok:
            r.save_marker(db, session, to_seq)
            _mark_agent_used(db, r.agent_id)
            any_sent = True
        db.commit()
        db.refresh(seg)
        results.append({"agent_id": str(r.agent_id) if r.agent_id else None,
                        "agent_name": r.name, "ok": ok, "segment_id": seg.id,
                        "words": words, "from_seq": from_seq, "to_seq": to_seq,
                        "error": err, "agent_msg_id": msg_id})

    out = {"ok": any_sent, "recipients": results,
           "sent_count": sum(1 for x in results if x.get("ok") and not x.get("skipped")),
           "failed_count": sum(1 for x in results if not x.get("ok"))}
    if not any_text:
        out["reason"] = "متنی برای ارسال نیست"
    if not any_sent and any_text:
        out["reason"] = "ارسال به هیچ ایجنت موفق نشد"
    return out


def flush_to_agent(db: Session, session: LiveSession, trigger: str = "manual") -> dict:
    """سازگاری با مسیر تک‌ایجنت. حالا چند ایجنت را هم پوشش می‌دهد."""
    res = flush_to_agents(db, session, trigger)
    first = next((x for x in res.get("recipients") or [] if not x.get("skipped")), None)
    if first:
        for k2 in ("segment_id", "words", "from_seq", "to_seq", "error", "agent_msg_id"):
            if k2 in first:
                res.setdefault(k2, first[k2])
    return res


# ---------- پیام کنترل (شروع جلسه و آزمون) ----------

def send_control_message(db: Session, session: LiveSession, text: str,
                         trigger: str) -> dict:
    """یک پیام کوتاه کنترلی را به همه ایجنت‌های نشست می‌فرستد و ثبت می‌کند.

    چرا بازه (segment) هم ساخته می‌شود: پاسخ ایجنت با reply_to به شناسه پیام
    ما برمی‌گردد و sync_replies فقط بازه‌های دارای amp_msg_id را می‌خواند.
    اگر بازه نسازیم، پاسخ ایجنت گم می‌شود و کاربر فکر می‌کند ایجنت جواب نداده.
    """
    recs = recipients(db, session)
    if not recs:
        return {"ok": False, "reason": "هیچ ایجنتی برای این نشست انتخاب نشده",
                "recipients": []}

    results: list[dict] = []
    any_sent = False
    # تایم اوت کوتاه: این پیام پشت دکمه ضبط است و کاربر نباید معطل بماند.
    for r in recs:
        ok, err, msg_id = send_to_agent(db, session, r, text, trigger, timeout=12.0)
        seg = LiveSegment(
            session_id=session.id, from_seq=-1, to_seq=-1, from_s=0, to_s=0,
            text=text, words=count_words(text), trigger=trigger,
            sent_to_agent=ok, send_error=None if ok else err,
            amp_msg_id=msg_id, agent_id=r.agent_id, agent_name=r.name,
        )
        db.add(seg)
        if ok:
            _mark_agent_used(db, r.agent_id)
            any_sent = True
        db.commit()
        db.refresh(seg)
        results.append({"agent_id": str(r.agent_id) if r.agent_id else None,
                        "agent_name": r.name, "ok": ok, "segment_id": seg.id,
                        "error": err, "agent_msg_id": msg_id})

    out = {"ok": any_sent, "recipients": results,
           "sent_count": sum(1 for x in results if x.get("ok")),
           "failed_count": sum(1 for x in results if not x.get("ok"))}
    if not any_sent:
        out["reason"] = "ارسال به هیچ ایجنت موفق نشد"
    return out


def notify_meeting_started(db: Session, session: LiveSession) -> dict:
    """پیام شروع جلسه را به ایجنت‌های انتخاب‌شده می‌فرستد.

    بدون این پیام، ایجنت تا رسیدن اولین آستانه هیچ خبری از جلسه ندارد و
    کاربر هم نمی‌داند اتصال برقرار است یا نه. این پیام هم اتصال را ثابت
    می‌کند هم زمینه جلسه را به ایجنت می‌دهد تا از ابتدا همراه باشد.
    """
    title = (session.title or "").strip() or "بدون عنوان"
    body = (
        f"[جلسه زنده — شروع]\n"
        f"جلسه «{title}» همین حالا شروع شد. آماده باش.\n"
        f"شناسه جلسه: {session.id}\n"
        f"این جلسه برای کاربر {session.user_id} است. "
        f"برای خواندن متن تازه ابزار meeting_transcript(شناسه جلسه, since_seq) را صدا کن. "
        f"سرور MCP: {_mcp_url()}\n"
        f"از این لحظه متن جلسه در تکه‌های بعدی برایت می‌آید. "
        f"پاسخ کوتاه، عملیاتی و بدون مقدمه بده."
    )
    return send_control_message(db, session, body, "meeting-start")


def send_test_message(db: Session, session: LiveSession) -> dict:
    """یک پیام آزمایشی کوتاه می‌فرستد تا کاربر بدون صحبت کردن اتصال را بسنجد.

    قبلا برای فهمیدن سالم بودن مسیر، کاربر باید نیم دقیقه حرف می‌زد تا
    آستانه رد شود. این پیام همان مسیر واقعی را با یک متن کوتاه می‌آزماید.
    """
    title = (session.title or "").strip() or "بدون عنوان"
    body = (
        f"[جلسه زنده — آزمون]\n"
        f"این یک پیام آزمایشی از جلسه «{title}» است. اگر این را می‌بینی، "
        f"مسیر ارسال سالم است. یک پاسخ کوتاه بده تا کاربر مطمئن شود.\n"
        f"شناسه جلسه: {session.id}\n"
        f"سرور MCP: {_mcp_url()}"
    )
    return send_control_message(db, session, body, "test")
