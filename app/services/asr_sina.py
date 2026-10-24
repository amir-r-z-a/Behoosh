"""کلاینت سرویس ASR سینا (shenava-koochik-v1.0).

مشخصات از سند SINA-ASR-API.md. نکات مهمی که در پیاده‌سازی رعایت شده:
- کار ناهمگام است: POST /v1/jobs بعد GET /v1/jobs/{id} تا done.
- نتیجه ۲۴ ساعته پاک می‌شود، پس متن همان لحظه در بهوش ذخیره می‌شود.
- job در حافظه سرویس است؛ ری‌استارت سرویس یعنی ۴۰۴. پس خطا باید مدیریت شود.
- words شامل entries نوع spacing هم هست؛ شمارش کلمه باید filter کند.
- عدد را حرفی می‌نویسد و نقطه‌گذاری ندارد (لایه پس‌پردازش جدا).
"""
import os
import time

import httpx


class SinaError(RuntimeError):
    pass


def _base() -> str:
    return os.getenv("SINA_ASR_URL", "http://5.34.200.60:16001").rstrip("/")


def _key() -> str:
    k = os.getenv("SINA_ASR_KEY", "").strip()
    if not k:
        raise SinaError("SINA_ASR_KEY تنظیم نشده")
    return k


def _headers() -> dict:
    return {"X-API-Key": _key()}


def health(timeout: float = 10.0) -> dict:
    r = httpx.get(f"{_base()}/health", timeout=timeout)
    r.raise_for_status()
    return r.json()


def submit(audio: bytes, filename: str, content_type: str = "audio/webm",
           diarize: bool = False, num_speakers: int | None = None,
           timeout: float = 120.0) -> dict:
    """ارسال تکه صدا. پاسخ: {id, status, ...}"""
    files = {"file": (filename, audio, content_type)}
    data = {"diarize": "true" if diarize else "false"}
    if num_speakers:
        data["num_speakers"] = str(num_speakers)
    r = httpx.post(f"{_base()}/v1/jobs", files=files, data=data,
                   headers=_headers(), timeout=timeout)
    if r.status_code == 413:
        raise SinaError("حجم تکه بیش از ۵۱۲ مگابایت")
    if r.status_code == 429:
        raise SinaError("صف سینا پر است")
    if r.status_code >= 400:
        raise SinaError(f"سینا {r.status_code}: {r.text[:200]}")
    return r.json()


def job(job_id: str, timeout: float = 30.0) -> dict:
    r = httpx.get(f"{_base()}/v1/jobs/{job_id}", headers=_headers(), timeout=timeout)
    if r.status_code == 404:
        raise SinaError("job پیدا نشد (احتمالا سرویس ری‌استارت شده)")
    r.raise_for_status()
    return r.json()


def result(job_id: str, timeout: float = 60.0) -> dict:
    r = httpx.get(f"{_base()}/v1/jobs/{job_id}/result", headers=_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()


def transcribe(audio: bytes, filename: str, content_type: str = "audio/webm",
               diarize: bool = False, num_speakers: int | None = None,
               poll_interval: float = 0.35, max_wait: float = 120.0) -> dict:
    """ارسال و انتظار تا پایان. برمی‌گرداند: {text, words, word_count, speakers, raw}"""
    j = submit(audio, filename, content_type, diarize, num_speakers)
    job_id = j.get("id")
    if not job_id:
        raise SinaError(f"پاسخ سینا بدون id: {str(j)[:200]}")

    deadline = time.time() + max_wait
    rec = j
    while time.time() < deadline:
        rec = job(job_id)
        st = rec.get("status")
        if st in ("done", "error"):
            break
        time.sleep(poll_interval)
    else:
        raise SinaError("مهلت انتظار سینا تمام شد")

    if rec.get("status") == "error":
        raise SinaError(f"سینا خطا داد: {rec.get('error')}")

    url = rec.get("result_url")
    if not url:
        raise SinaError("result_url خالی است")
    res = result(job_id)
    entries = res.get("words") or []
    real_words = [w for w in entries if w.get("type") == "word"]
    meta = rec.get("meta") or {}
    return {
        "text": (res.get("text") or "").strip(),
        "word_count": len(real_words) or int(meta.get("word_count") or 0),
        "speakers": (meta.get("speakers") or []),
        "duration_s": meta.get("duration_s"),
        "raw": res,
    }
