"""سرور MCP مالی بهوش (streamable-http). پورت ۸۰۷۸.

جدا از MCP سلامت. توکن جدا، scope جدا. اگر یکی خراب شود، دیگری دست‌نخورده می‌ماند.
پیش‌فرض read-only: تول‌های نوشتن فقط با توکن scope دار کار می‌کنند و API خودش
۴۰۳ برمی‌گرداند اگر scope نباشد.
"""
import json
import os

from mcp.server.fastmcp import FastMCP

from app.mcp import _auth, _client

# توکن از هدر درخواست کاربر خوانده می‌شود (app/mcp/_auth.py).
_auth.set_env_token(os.getenv("FINANCE_API_TOKEN", ""))

mcp = FastMCP("behoosh-finance", host="0.0.0.0", port=8002)


def _req(method: str, path: str, body: dict | None = None, params: dict | None = None):
    return _client.request(method, f"/finance{path}", body=body, params=params)


def _get(path: str, params: dict | None = None):
    return json.dumps(_req("GET", path, params=params), ensure_ascii=False)


def _post(path: str, body: dict):
    return json.dumps(_req("POST", path, body=body), ensure_ascii=False)


# ---------- خواندن ----------

@mcp.tool()
def finance_accounts_list(active_only: bool = True) -> str:
    """لیست حساب‌ها با موجودی محاسبه‌شده. نوع حساب: asset|expense|income|liability."""
    return _get("/accounts", {"active_only": active_only})


@mcp.tool()
def finance_balance_get(account_id: str | None = None) -> str:
    """موجودی یک حساب یا همه حساب‌ها."""
    return _get("/balance", {"account_id": account_id} if account_id else None)


@mcp.tool()
def finance_transactions_list(start: str | None = None, end: str | None = None,
                              account_id: str | None = None, category_id: str | None = None,
                              direction: str | None = None, limit: int = 100) -> str:
    """لیست تراکنش‌ها. تاریخ‌ها ISO مثل 2026-10-17. direction: debit|credit."""
    p = {"limit": limit}
    for k, v in (("start", start), ("end", end), ("account_id", account_id),
                 ("category_id", category_id), ("direction", direction)):
        if v:
            p[k] = v
    return _get("/transactions", p)


@mcp.tool()
def finance_summary_get(start: str | None = None, end: str | None = None,
                        from_jalali: str | None = None, to_jalali: str | None = None,
                        period: str | None = None) -> str:
    """خلاصه مالی: درآمد، هزینه، خالص، تفکیک دسته.
    بازه را شمسی بده: from_jalali=1405/07/01 و to_jalali=1405/07/25.
    period می‌تواند week|month|year باشد."""
    p = {}
    if period:
        p["period"] = period
    if start:
        p["start"] = start
    if end:
        p["end"] = end
    if from_jalali:
        p["from_jalali"] = from_jalali
    if to_jalali:
        p["to_jalali"] = to_jalali
    return _get("/summary", p or None)


@mcp.tool()
def finance_budget_status(start: str | None = None, end: str | None = None,
                          from_jalali: str | None = None,
                          to_jalali: str | None = None) -> str:
    """وضعیت بودجه هر دسته در برابر واقعی. بازه شمسی هم پذیرفته می‌شود."""
    p = {}
    if start:
        p["start"] = start
    if end:
        p["end"] = end
    if from_jalali:
        p["from_jalali"] = from_jalali
    if to_jalali:
        p["to_jalali"] = to_jalali
    return _get("/budget", p or None)


@mcp.tool()
def finance_categories_list(kind: str | None = None) -> str:
    """لیست دسته‌ها. kind: expense|income."""
    return _get("/categories", {"kind": kind} if kind else None)


@mcp.tool()
def finance_raw_messages(unparsed_only: bool = False, limit: int = 50) -> str:
    """پیامک‌های خام بانک. با unparsed_only صف دسته‌بندی را ببین."""
    return _get("/raw", {"unparsed_only": unparsed_only, "limit": limit})


@mcp.tool()
def finance_audit_log(limit: int = 50) -> str:
    """هر نوشتن ایجنت در این لاگ است."""
    return _get("/audit", {"limit": limit})


# ---------- نوشتن ----------

@mcp.tool()
def finance_transaction_log(occurred_at: str, amount: float, direction: str,
                            account_id: str, counter_account_id: str | None = None,
                            category_id: str | None = None, description: str = "",
                            counterparty: str | None = None,
                            external_ref: str | None = None,
                            is_transfer: bool = False,
                            liability_id: str | None = None,
                            exclude_from_summary: bool | None = None) -> str:
    """ثبت یک تراکنش متوازن. مبلغ همیشه مثبت. direction: debit|credit.
    external_ref شماره پیگیری بانک است؛ اگر تکراری باشد ثبت نمی‌شود.
    exclude_from_summary: اگر true باشد از خلاصه درآمد/هزینه بیرون می‌رود.
    خودکار: دریافت اصل وام (credit + liability_id) درآمد نیست و خارج می‌شود."""
    body = {"occurred_at": occurred_at, "amount": amount, "direction": direction,
            "account_id": account_id, "description": description, "source": "agent"}
    for k, v in (("counter_account_id", counter_account_id), ("category_id", category_id),
                 ("counterparty", counterparty), ("external_ref", external_ref),
                 ("liability_id", liability_id)):
        if v:
            body[k] = v
    if is_transfer:
        body["is_transfer"] = True
    if exclude_from_summary is not None:
        body["exclude_from_summary"] = exclude_from_summary
    return _post("/transaction", body)


@mcp.tool()
def finance_transactions_log_batch(items: list[dict]) -> str:
    """ثبت گروهی تراکنش. هر آیتم مثل finance_transaction_log."""
    return _post("/transactions/batch", {"items": items})


@mcp.tool()
def finance_sms_log(body: str, received_at: str | None = None, bank: str | None = None,
                    parsed: dict | None = None) -> str:
    """ثبت پیامک بانک. متن خام همیشه ذخیره می‌شود.
    parsed اختیاری: occurred_at, amount, direction, account_id, category_id,
    description, counterparty, external_ref. اگر بدهی، تراکنش هم ساخته می‌شود."""
    payload = {"body": body}
    for k, v in (("received_at", received_at), ("bank", bank), ("parsed", parsed)):
        if v:
            payload[k] = v
    return _post("/sms", payload)


@mcp.tool()
def finance_account_create(name: str, type: str, currency: str = "IRT",
                           card_last4: str | None = None,
                           opening_balance: float = 0) -> str:
    """ساخت حساب. type: asset|expense|income|liability."""
    body = {"name": name, "type": type, "currency": currency,
            "opening_balance": opening_balance}
    if card_last4:
        body["card_last4"] = card_last4
    return _post("/account", body)


@mcp.tool()
def finance_category_create(name: str, kind: str, parent_id: str | None = None) -> str:
    """ساخت دسته. kind: expense|income."""
    body = {"name": name, "kind": kind}
    if parent_id:
        body["parent_id"] = parent_id
    return _post("/category", body)


@mcp.tool()
def finance_budget_set(category_id: str, amount: float, period: str = "monthly") -> str:
    """تعیین بودجه دسته. period: weekly|monthly|yearly."""
    return _post("/budget", {"category_id": category_id, "amount": amount,
                             "period": period})


@mcp.tool()
def finance_transaction_correct(transaction_id: str | None = None,
                                description: str | None = None,
                                category_id: str | None = None,
                                counterparty: str | None = None,
                                exclude_from_summary: bool | None = None,
                                tx_id: str | None = None) -> str:
    """اصلاح تراکنش. حذف وجود ندارد. اصلاح در audit ثبت می‌شود.
    با exclude_from_summary می‌توان تراکنش را از خلاصه درآمد/هزینه بیرون برد
    (مثلا دریافت اصل وام که درآمد نیست). tx_id نام قدیمی است و هنوز کار می‌کند."""
    tid = transaction_id or tx_id
    if not tid:
        return json.dumps({"ok": False, "error": "transaction_id لازم است"},
                          ensure_ascii=False)
    body = {}
    for k, v in (("description", description), ("category_id", category_id),
                 ("counterparty", counterparty),
                 ("exclude_from_summary", exclude_from_summary)):
        if v is not None:
            body[k] = v
    return json.dumps(_req("PATCH", f"/transaction/{tid}", body=body), ensure_ascii=False)


# ---------- بدهی و تعهد ----------

@mcp.tool()
def finance_liabilities_list(status: str | None = None) -> str:
    """بدهی‌ها با مانده، تعداد قسط پرداخت‌شده و سررسید بعدی.
    status: active|settled. مانده کل جدا از هزینه گزارش می‌شود."""
    return _get("/liabilities", {"status": status} if status else None)


@mcp.tool()
def finance_liability_get(liability_id: str) -> str:
    """جزئیات یک بدهی."""
    return _get(f"/liabilities/{liability_id}")


@mcp.tool()
def finance_liability_create(name: str, principal: float,
                             installments_total: int = 0,
                             installment_amount: float = 0,
                             interest_rate: float = 0,
                             start_date: str | None = None,
                             due_day: int | None = None,
                             account_id: str | None = None,
                             kind: str = "loan",
                             note: str | None = None) -> str:
    """ثبت وام یا تعهد. اصل مبلغ بدهی است نه درآمد.
    تاریخ شمسی (1405/07/25) یا میلادی (2026-10-17) هر دو قبول است."""
    body = {"name": name, "principal": principal,
            "installments_total": installments_total,
            "installment_amount": installment_amount,
            "interest_rate": interest_rate, "kind": kind}
    for k, v in (("start_date", start_date), ("due_day", due_day),
                 ("account_id", account_id), ("note", note)):
        if v is not None:
            body[k] = v
    return _post("/liability", body)


@mcp.tool()
def finance_liability_update(liability_id: str, name: str | None = None,
                             principal: float | None = None,
                             installments_total: int | None = None,
                             installment_amount: float | None = None,
                             interest_rate: float | None = None,
                             due_day: int | None = None,
                             status: str | None = None,
                             note: str | None = None) -> str:
    """اصلاح بدهی. برای تسویه کامل status=settled بده."""
    body = {}
    for k, v in (("name", name), ("principal", principal),
                 ("installments_total", installments_total),
                 ("installment_amount", installment_amount),
                 ("interest_rate", interest_rate), ("due_day", due_day),
                 ("status", status), ("note", note)):
        if v is not None:
            body[k] = v
    return json.dumps(_req("PATCH", f"/liability/{liability_id}", body=body),
                      ensure_ascii=False)


@mcp.tool()
def finance_transfer(from_account_id: str, to_account_id: str, amount: float,
                     occurred_at: str, description: str = "") -> str:
    """انتقال بین حساب‌های خود کاربر. هزینه نیست و در جمع هزینه نمی‌آید.
    تاریخ شمسی یا میلادی قبول است."""
    return _post("/transaction", {
        "occurred_at": occurred_at, "amount": amount, "direction": "debit",
        "account_id": from_account_id, "counter_account_id": to_account_id,
        "description": description or "انتقال داخلی", "is_transfer": True,
    })


if __name__ == "__main__":
    _auth.serve(mcp, 8002)
