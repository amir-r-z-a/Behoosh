"""مسیرهای مالی. اسکیمای جدا، scope جدا از سلامت.

هر مسیر با scope خودش باز می‌شود. user_id همیشه از توکن می‌آید.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    SCOPE_FINANCE_READ, SCOPE_FINANCE_WRITE, Principal, require_scope,
)
from app.db.finance_models import (
    FinAccount, FinAudit, FinBudget, FinCategory, FinEntry, FinRawMessage, FinTransaction,
)
from app.db.session import get_db
from app.services import finance as svc
from app.services import jalali
from app.services.sms_parser import parse_sms

read = APIRouter(prefix="/v1/finance", tags=["finance"],
                 dependencies=[Depends(require_scope(SCOPE_FINANCE_READ))])
write = APIRouter(prefix="/v1/finance", tags=["finance"],
                  dependencies=[Depends(require_scope(SCOPE_FINANCE_WRITE))])


# نام‌های ساده‌ای که کاربر عادی به کار می‌برد. کاربر نباید بداند که
# مدل دفتر چهار نوع حساب دارد؛ ما نام ساده را به نوع درست نگاشت می‌کنیم.
ACCOUNT_TYPE_ALIASES = {
    # دارایی: هر جا پول نگه می‌داری
    "bank": "asset", "card": "asset", "cash": "asset", "wallet": "asset",
    "savings": "asset", "deposit": "asset", "account": "asset", "asset": "asset",
    "بانک": "asset", "کارت": "asset", "نقد": "asset", "کیف پول": "asset",
    "پس‌انداز": "asset", "سپرده": "asset", "حساب": "asset", "دارایی": "asset",
    # بدهی
    "loan": "liability", "debt": "liability", "liability": "liability",
    "وام": "liability", "بدهی": "liability", "تسهیلات": "liability",
    # درآمد و هزینه
    "income": "income", "درآمد": "income",
    "expense": "expense", "هزینه": "expense",
}


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    # هم نام ساده (بانک، نقد، وام) و هم نام فنی (asset, liability) پذیرفته می‌شود.
    type: str = Field(min_length=1, max_length=40)
    currency: str = "IRT"
    card_last4: str | None = None
    opening_balance: float = 0

    def resolved_type(self) -> str:
        raw = (self.type or "").strip().lower()
        if raw in ACCOUNT_TYPE_ALIASES:
            return ACCOUNT_TYPE_ALIASES[raw]
        raise HTTPException(422, f"نوع حساب نامعتبر: {self.type}. "
                                 "یکی از این‌ها را بده: بانک، نقد، کارت، پس‌انداز، وام، درآمد، هزینه")


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern="^(expense|income)$")
    parent_id: str | None = None


class TxIn(BaseModel):
    # رشته قبول است تا تاریخ شمسی (1405/07/25) هم بیاید؛ تبدیل در سرویس.
    occurred_at: str | datetime
    amount: float = Field(gt=0)
    direction: str = Field(pattern="^(debit|credit)$")
    account_id: str
    counter_account_id: str | None = None
    category_id: str | None = None
    description: str = ""
    counterparty: str | None = None
    source: str = "manual"
    external_ref: str | None = None
    # انتقال بین حساب‌های خود کاربر هزینه نیست.
    is_transfer: bool = False
    # اگر این تراکنش قسط یک وام است، شناسه وام.
    liability_id: str | None = None


class TxBatchIn(BaseModel):
    items: list[TxIn] = Field(min_length=1, max_length=200)


class SmsIn(BaseModel):
    body: str = Field(min_length=1)
    received_at: datetime | None = None
    bank: str | None = None
    parsed: dict | None = None


class BudgetIn(BaseModel):
    category_id: str
    period: str = "monthly"
    amount: float = Field(ge=0)


class LiabilityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    principal: float = Field(ge=0)
    installments_total: int = 0
    installment_amount: float = 0
    interest_rate: float = 0
    start_date: str | None = None
    due_day: int | None = None
    account_id: str | None = None
    kind: str = "loan"
    note: str | None = None


class LiabilityPatchIn(BaseModel):
    name: str | None = None
    principal: float | None = None
    installments_total: int | None = None
    installment_amount: float | None = None
    interest_rate: float | None = None
    due_day: int | None = None
    status: str | None = None
    note: str | None = None


class CorrectIn(BaseModel):
    description: str | None = None
    category_id: str | None = None
    counterparty: str | None = None
    # دریافت اصل وام درآمد نیست؛ این پرچم تراکنش را از خلاصه بیرون می‌برد.
    exclude_from_summary: bool | None = None


def _rng(start: str | None, end: str | None,
         from_jalali: str | None = None, to_jalali: str | None = None) -> tuple:
    """بازه را می‌سازد. اولویت: پارامتر شمسی، بعد میلادی، بعد پیش‌فرض ماه شمسی.

    چرا پیش‌فرض ماه شمسی است: کاربر ایرانی ماه مالی‌اش شمسی است. اگر پیش‌فرض
    را اول ماه میلادی بگذاریم، گزارش «این ماه» از نیمه ماه شمسی شروع می‌شود.
    """
    today = date.today()
    s = from_jalali or start
    e = to_jalali or end
    if not s:
        s = jalali.month_bounds_jalali(today)[0].isoformat()
    if not e:
        e = today.isoformat()
    return s, e


@read.get("/accounts")
def accounts(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
             db: Session = Depends(get_db), active_only: bool = True):
    """حساب‌ها با موجودی محاسبه‌شده."""
    rows = db.execute(select(FinAccount).where(
        FinAccount.user_id == p.user_id,
        *( [FinAccount.active.is_(True)] if active_only else [] )
    ).order_by(FinAccount.created_at)).scalars().all()
    bal = {b["id"]: b["balance"] for b in svc.balance_of(db, p.user_id)}
    return {"accounts": [
        {"id": str(a.id), "name": a.name, "type": a.type, "currency": a.currency,
         "card_last4": a.card_last4, "balance": bal.get(str(a.id), 0.0)}
        for a in rows
    ]}


@read.get("/balance")
def balance(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
            db: Session = Depends(get_db), account_id: str | None = None):
    """موجودی یک حساب یا همه."""
    return {"balances": svc.balance_of(db, p.user_id, account_id)}


@read.get("/transactions")
def transactions(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
                 db: Session = Depends(get_db),
                 start: str | None = None, end: str | None = None,
                 account_id: str | None = None, category_id: str | None = None,
                 direction: str | None = None, limit: int = Query(100, le=500),
                 offset: int = 0):
    """لیست تراکنش‌ها با فیلتر."""
    s, e = _rng(start, end)
    q = select(FinTransaction).where(
        FinTransaction.user_id == p.user_id,
        FinTransaction.occurred_at >= svc._as_dt(s),
        FinTransaction.occurred_at <= svc._as_dt(e) + timedelta(days=1),
    )
    if category_id:
        q = q.where(FinTransaction.category_id == category_id)
    q = q.order_by(FinTransaction.occurred_at.desc()).limit(limit).offset(offset)

    cats = {c.id: c.name for c in db.execute(
        select(FinCategory).where(FinCategory.user_id == p.user_id)).scalars().all()}
    out = []
    for tx in db.execute(q).scalars().all():
        ents = db.execute(select(FinEntry).where(
            FinEntry.transaction_id == tx.id)).scalars().all()
        if account_id and not any(str(x.account_id) == account_id for x in ents):
            continue
        if direction and not any(x.direction == direction for x in ents):
            continue
        out.append({
            "id": str(tx.id), "occurred_at": tx.occurred_at,
            "description": tx.description, "counterparty": tx.counterparty,
            "category": cats.get(tx.category_id), "source": tx.source,
            "external_ref": tx.external_ref,
            "amount": float(max((x.amount for x in ents), default=0)),
            "direction": next((x.direction for x in ents), None),
        })
    return {"transactions": out, "count": len(out)}


@read.get("/summary")
def summary(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
            db: Session = Depends(get_db),
            start: str | None = None, end: str | None = None,
            from_jalali: str | None = None, to_jalali: str | None = None,
            period: str | None = None):
    """درآمد، هزینه، خالص، تفکیک دسته.
    بازه را می‌توان شمسی داد: from_jalali=1405/07/01&to_jalali=1405/07/25."""
    if period == "week":
        today = date.today()
        s = (today - timedelta(days=7)).isoformat()
        e = today.isoformat()
    elif period == "year":
        today = date.today()
        s = jalali.month_bounds_jalali(today.replace(month=1, day=1))[0].isoformat()
        e = today.isoformat()
    else:
        s, e = _rng(start, end, from_jalali, to_jalali)
    return svc.summary(db, p.user_id, s, e)


@read.get("/budget")
def budget(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
           db: Session = Depends(get_db),
           start: str | None = None, end: str | None = None,
           from_jalali: str | None = None, to_jalali: str | None = None):
    """وضعیت بودجه هر دسته. بازه شمسی هم پذیرفته می‌شود."""
    s, e = _rng(start, end, from_jalali, to_jalali)
    return {"budgets": svc.budget_status(db, p.user_id, s, e)}


@read.get("/liabilities")
def liabilities(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
                db: Session = Depends(get_db), status: str | None = None):
    """بدهی‌ها با مانده و سررسید بعدی. مانده کل جدا از هزینه است."""
    return svc.liabilities_list(db, p.user_id, status)


@read.get("/liabilities/{liability_id}")
def liability_one(liability_id: str,
                  p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
                  db: Session = Depends(get_db)):
    """یک بدهی با جزئیات."""
    row = svc.get_liability(db, p.user_id, liability_id)
    return {"liability": svc.liability_view(db, p.user_id, row)}


@write.post("/liability", status_code=201)
def liability_new(payload: LiabilityIn,
                  p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                  db: Session = Depends(get_db)):
    """ثبت وام یا تعهد. اصل مبلغ بدهی است، نه درآمد."""
    return svc.liability_create(
        db, p.user_id, name=payload.name, principal=payload.principal,
        installments_total=payload.installments_total,
        installment_amount=payload.installment_amount,
        interest_rate=payload.interest_rate, start_date=payload.start_date,
        due_day=payload.due_day, account_id=payload.account_id,
        kind=payload.kind, note=payload.note, token_id=p.token_id,
    )


@write.patch("/liability/{liability_id}")
def liability_edit(liability_id: str, payload: LiabilityPatchIn,
                   p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                   db: Session = Depends(get_db)):
    """اصلاح بدهی. تسویه با status=settled."""
    return svc.liability_update(
        db, p.user_id, liability_id, name=payload.name,
        principal=payload.principal, installments_total=payload.installments_total,
        installment_amount=payload.installment_amount,
        interest_rate=payload.interest_rate, due_day=payload.due_day,
        status=payload.status, note=payload.note, token_id=p.token_id,
    )


@read.get("/categories")
def categories(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
               db: Session = Depends(get_db), kind: str | None = None):
    """دسته‌ها."""
    q = select(FinCategory).where(FinCategory.user_id == p.user_id)
    if kind:
        q = q.where(FinCategory.kind == kind)
    rows = db.execute(q.order_by(FinCategory.name)).scalars().all()
    return {"categories": [
        {"id": str(c.id), "name": c.name, "kind": c.kind,
         "parent_id": str(c.parent_id) if c.parent_id else None} for c in rows
    ]}


@read.get("/raw")
def raw_messages(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
                 db: Session = Depends(get_db), unparsed_only: bool = False,
                 limit: int = Query(50, le=200)):
    """پیامک‌های خام. صف دسته‌بندی."""
    q = select(FinRawMessage).where(FinRawMessage.user_id == p.user_id)
    if unparsed_only:
        q = q.where(FinRawMessage.parsed.is_(False))
    rows = db.execute(q.order_by(FinRawMessage.received_at.desc()).limit(limit)).scalars().all()
    return {"messages": [
        {"id": str(r.id), "bank": r.bank, "body": r.body, "received_at": r.received_at,
         "parsed": r.parsed, "parse_error": r.parse_error} for r in rows
    ]}


@read.get("/audit")
def audit_log(p: Principal = Depends(require_scope(SCOPE_FINANCE_READ)),
              db: Session = Depends(get_db), limit: int = Query(50, le=200)):
    """هر نوشتن ایجنت اینجا هست."""
    rows = db.execute(select(FinAudit).where(FinAudit.user_id == p.user_id)
                      .order_by(FinAudit.created_at.desc()).limit(limit)).scalars().all()
    return {"audit": [
        {"id": str(a.id), "actor": a.actor, "tool": a.tool, "payload": a.payload,
         "created_at": a.created_at} for a in rows
    ]}


@write.post("/transaction", status_code=201)
def log_transaction(payload: TxIn,
                    p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                    db: Session = Depends(get_db)):
    """ثبت یک تراکنش متوازن."""
    return svc.log_transaction(
        db, p.user_id, occurred_at=payload.occurred_at, amount=payload.amount,
        direction=payload.direction, account_id=payload.account_id,
        counter_account_id=payload.counter_account_id, category_id=payload.category_id,
        description=payload.description, counterparty=payload.counterparty,
        source=payload.source, external_ref=payload.external_ref,
        is_transfer=payload.is_transfer, liability_id=payload.liability_id,
        token_id=p.token_id,
    )


@write.post("/transactions/batch", status_code=201)
def log_batch(payload: TxBatchIn,
              p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
              db: Session = Depends(get_db)):
    """ثبت گروهی. برای وقتی ایجنت چند پیامک را یک‌جا خوانده."""
    results = []
    for it in payload.items:
        try:
            results.append(svc.log_transaction(
                db, p.user_id, occurred_at=it.occurred_at, amount=it.amount,
                direction=it.direction, account_id=it.account_id,
                counter_account_id=it.counter_account_id, category_id=it.category_id,
                description=it.description, counterparty=it.counterparty,
                is_transfer=it.is_transfer, liability_id=it.liability_id,
                source=it.source, external_ref=it.external_ref, token_id=p.token_id,
            ))
        except HTTPException as e:
            results.append({"ok": False, "error": e.detail, "ref": it.external_ref})
    ok = sum(1 for r in results if r.get("ok"))
    return {"ok": True, "recorded": ok, "failed": len(results) - ok, "results": results}


@write.post("/sms", status_code=201)
def log_sms(payload: SmsIn,
            p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
            db: Session = Depends(get_db)):
    """پیامک خام بانک.

    اگر parsed بدهی همان استفاده می‌شود. وگرنه خودکار پارس می‌شود. متن خام
    در هر حالت ذخیره می‌شود، پس داده از دست نمی‌رود.
    """
    parsed = payload.parsed
    if parsed is None:
        parsed = parse_sms(payload.body)
        if parsed:
            # حساب را از چهار رقم آخر کارت پیدا می‌کنیم. اگر نبود، اولین
            # حساب دارایی فعال. اگر هیچ حسابی نبود، فقط خام ذخیره می‌شود.
            acc = None
            last4 = parsed.get("card_last4")
            if last4:
                acc = db.execute(select(FinAccount).where(
                    FinAccount.user_id == p.user_id,
                    FinAccount.card_last4 == last4,
                    FinAccount.active.is_(True))).scalars().first()
            if acc is None:
                acc = db.execute(select(FinAccount).where(
                    FinAccount.user_id == p.user_id, FinAccount.type == "asset",
                    FinAccount.active.is_(True)).order_by(FinAccount.created_at)).scalars().first()
            if acc is None:
                parsed = None
            else:
                parsed["account_id"] = str(acc.id)
                parsed.pop("unit", None)
                parsed.pop("raw_amount", None)
                parsed.pop("balance", None)
                parsed.pop("card_last4", None)

    return svc.log_sms(db, p.user_id, body=payload.body, received_at=payload.received_at,
                       bank=payload.bank, parsed=parsed, token_id=p.token_id)


@write.post("/account", status_code=201)
def create_account(payload: AccountIn,
                   p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                   db: Session = Depends(get_db)):
    """حساب جدید."""
    dup = db.execute(select(FinAccount).where(
        FinAccount.user_id == p.user_id, FinAccount.name == payload.name)).scalar_one_or_none()
    if dup:
        raise HTTPException(409, "account name exists")
    a = FinAccount(user_id=p.user_id, name=payload.name, type=payload.resolved_type(),
                   currency=payload.currency, card_last4=payload.card_last4,
                   opening_balance=payload.opening_balance)
    db.add(a)
    svc.audit(db, p.user_id, "finance_account_create", {"name": payload.name},
              token_id=p.token_id)
    db.commit()
    return {"ok": True, "account_id": str(a.id)}


@write.post("/category", status_code=201)
def create_category(payload: CategoryIn,
                    p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                    db: Session = Depends(get_db)):
    """دسته جدید."""
    c = FinCategory(user_id=p.user_id, name=payload.name, kind=payload.kind,
                    parent_id=payload.parent_id)
    db.add(c)
    svc.audit(db, p.user_id, "finance_category_create", {"name": payload.name},
              token_id=p.token_id)
    db.commit()
    return {"ok": True, "category_id": str(c.id)}


@write.post("/budget", status_code=201)
def set_budget(payload: BudgetIn,
               p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
               db: Session = Depends(get_db)):
    """تعیین بودجه. اگر بود قبلی هست، به‌روز می‌شود."""
    row = db.execute(select(FinBudget).where(
        FinBudget.user_id == p.user_id, FinBudget.category_id == payload.category_id,
        FinBudget.period == payload.period)).scalar_one_or_none()
    if row is None:
        row = FinBudget(user_id=p.user_id, category_id=payload.category_id,
                        period=payload.period)
        db.add(row)
    row.amount = payload.amount
    row.active = True
    svc.audit(db, p.user_id, "finance_budget_set",
              {"category_id": payload.category_id, "amount": payload.amount},
              token_id=p.token_id)
    db.commit()
    return {"ok": True, "budget_id": str(row.id)}


@write.patch("/transaction/{tx_id}")
def correct_transaction(tx_id: str, payload: CorrectIn,
                        p: Principal = Depends(require_scope(SCOPE_FINANCE_WRITE)),
                        db: Session = Depends(get_db)):
    """اصلاح تراکنش. حذف نمی‌کند. در audit ثبت می‌شود."""
    tx = db.execute(select(FinTransaction).where(
        FinTransaction.id == tx_id, FinTransaction.user_id == p.user_id)).scalar_one_or_none()
    if tx is None:
        raise HTTPException(404, "transaction not found")
    changes = {}
    for f in ("description", "category_id", "counterparty", "exclude_from_summary"):
        v = getattr(payload, f)
        if v is not None:
            setattr(tx, f, v)
            changes[f] = v
    svc.audit(db, p.user_id, "finance_transaction_correct",
              {"transaction_id": tx_id, "changes": changes}, token_id=p.token_id)
    db.commit()
    return {"ok": True, "transaction_id": tx_id, "changes": changes}
