"""ابزارهای MCP دستیار جلسه زنده.

این ابزارها به ایجنت اجازه می‌دهند وسط جلسه متن را بخواند و نظر بدهد.
توکن از هدر درخواست می‌آید (app/mcp/_auth.py) و scope meeting لازم است.
"""
import json

import httpx

from app.mcp import _auth

API = None


def _api() -> str:
    import os
    return os.getenv("BEHOOSH_API", "http://api:8000")


def _req(method: str, path: str, body: dict | None = None, params: dict | None = None):
    r = httpx.request(method, f"{_api()}/v1/live{path}", json=body, params=params,
                      headers={"X-API-Key": _auth.current_token()}, timeout=60)
    if r.status_code >= 400:
        return {"ok": False, "status": r.status_code, "error": r.text[:400]}
    return r.json()


def register(mcp) -> None:
    """ابزارها را روی سرور MCP سلامت ثبت می‌کند."""

    @mcp.tool()
    def meeting_sessions_list(limit: int = 20) -> str:
        """لیست نشست‌های جلسه زنده کاربر با تعداد کلمه و وضعیت."""
        return json.dumps(_req("GET", "/sessions", params={"limit": limit}),
                          ensure_ascii=False)

    @mcp.tool()
    def meeting_session_get(session_id: str) -> str:
        """وضعیت کامل یک نشست: متن کامل، شمارنده، بازه‌های ارسال‌شده به ایجنت."""
        return json.dumps(_req("GET", f"/sessions/{session_id}"), ensure_ascii=False)

    @mcp.tool()
    def meeting_transcript(session_id: str, since_seq: int = 0) -> str:
        """متن جلسه از تکه شماره since_seq به بعد. برای خواندن زنده وسط جلسه."""
        return json.dumps(_req("GET", f"/sessions/{session_id}/transcript",
                               params={"since_seq": since_seq}), ensure_ascii=False)

    @mcp.tool()
    def meeting_ask_now(session_id: str) -> str:
        """متن معلق جلسه را همین حالا به ایجنت می‌فرستد. دکمه «الان نظر بده»."""
        return json.dumps(_req("POST", f"/sessions/{session_id}/flush"), ensure_ascii=False)

    @mcp.tool()
    def meeting_replies(session_id: str) -> str:
        """پاسخ‌های ایجنت به بازه‌های ارسال‌شده. اول از کانال AMP می‌کشد.

        ارسال غیرهمگام است، پس پاسخ با تاخیر می‌رسد. این ابزار پاسخ‌ها را
        از کانال AMP می‌خواند و به بازه درست می‌چسباند.
        """
        return json.dumps(_req("POST", f"/sessions/{session_id}/sync-replies"),
                          ensure_ascii=False)

    @mcp.tool()
    def meeting_stop(session_id: str) -> str:
        """پایان نشست. متن نهایی را برمی‌گرداند."""
        return json.dumps(_req("POST", f"/sessions/{session_id}/stop"), ensure_ascii=False)

    @mcp.tool()
    def meeting_agents_list(include_archived: bool = False) -> str:
        """دفترچه ایجنت‌های ثبت‌شده کاربر با نام و وضعیت توکن.

        توکن خام برنمی‌گردد، فقط چهار کاراکتر آخر. برای شروع جلسه با چند
        ایجنت، شناسه‌ها را از همین‌جا بردار.
        """
        return json.dumps(_req("GET", "/agents",
                               params={"include_archived": include_archived}),
                          ensure_ascii=False)

    @mcp.tool()
    def meeting_agent_add(name: str, token: str, note: str = "") -> str:
        """ثبت یک ایجنت در دفترچه کاربر. یک بار ثبت می‌شود و همیشه می‌ماند.

        پس از این، در هر جلسه فقط شناسه ایجنت انتخاب می‌شود و نیازی به
        دادن دوباره توکن نیست.
        """
        return json.dumps(_req("POST", "/agents",
                               body={"name": name, "token": token, "note": note or None}),
                          ensure_ascii=False)

    @mcp.tool()
    def meeting_agent_update(agent_id: str, name: str = "", token: str = "",
                             note: str | None = None) -> str:
        """ویرایش نام، یادداشت یا توکن یک ایجنت. فیلد خالی دست نمی‌خورد."""
        body: dict = {}
        if name:
            body["name"] = name
        if token:
            body["token"] = token
        if note is not None:
            body["note"] = note
        return json.dumps(_req("PATCH", f"/agents/{agent_id}", body=body),
                          ensure_ascii=False)

    @mcp.tool()
    def meeting_agent_test(agent_id: str) -> str:
        """توکن ایجنت را می‌آزماید. تازه‌ترین وضعیت را برمی‌گرداند."""
        return json.dumps(_req("POST", f"/agents/{agent_id}/test"), ensure_ascii=False)

    @mcp.tool()
    def meeting_agent_archive(agent_id: str) -> str:
        """بایگانی ایجنت. تاریخچه جلسات پاک نمی‌شود."""
        return json.dumps(_req("DELETE", f"/agents/{agent_id}"), ensure_ascii=False)

    @mcp.tool()
    def meeting_session_create(title: str = "", agent_ids: str = "",
                               word_threshold: int = 400, time_threshold_s: int = 90,
                               silence_threshold_s: int = 6,
                               min_words_to_send: int = 60) -> str:
        """ساخت نشست جلسه زنده با چند ایجنت مشارکت‌کننده.

        agent_ids را با کاما جدا کن، مثلا "id1,id2". خالی یعنی نشست بی‌ایجنت
        که می‌شود بعدا اضافه کرد. همه ایجنت‌ها باید در دفترچه کاربر باشند.
        """
        ids = [x.strip() for x in (agent_ids or "").split(",") if x.strip()]
        return json.dumps(_req("POST", "/sessions", body={
            "title": title or None, "agent_ids": ids,
            "word_threshold": word_threshold, "time_threshold_s": time_threshold_s,
            "silence_threshold_s": silence_threshold_s,
            "min_words_to_send": min_words_to_send,
        }), ensure_ascii=False)

    @mcp.tool()
    def meeting_health() -> str:
        """سلامت ماژول جلسه و دسترسی به سرویس صوت."""
        return json.dumps(_req("GET", "/health"), ensure_ascii=False)
