"""سرویس مالی: منطق دوبل‌انتری.

سه قاعده سخت که همه‌جا رعایت می‌شود:
۱. مبلغ همیشه مثبت است. جهت با فیلد direction می‌آید، نه با علامت.
۲. هر تراکنش باید متوازن باشد: جمع debit و credit برابر.
۳. هیچ حذفی وجود ندارد. فقط اصلاح، و اصلاح هم در audit ثبت می‌شود.
"""
import uuid
from datetime import timedelta, date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.finance_models import (
    FinAccount, FinAudit, FinBudget, FinCategory, FinEntry, FinLiability,
    FinRawMessage, FinTransaction,
)
from app.services.jalali import (parse_date, to_jalali_str, gregorian_to_jalali, month_bounds_jalali,
                                     jalali_to_gregorian)


COUNTER_ACCOUNT_NAMES = {"expense": "هزینه نامشخص", "income": "درآمد نامشخص"}


def audit(db: Session, user_id, tool: str, payload: dict, token_id=None,
          actor: str = "agent") -> None:
    """هر نوشتن اینجا ثبت می‌شود. الگو از open-finance."""
    db.add(FinAudit(user_id=user_id, actor=actor, token_id=token_id,
                    tool=tool, payload=payload))


def _as_dt(value, end: bool = False) -> datetime:
    """رشته یا تاریخ را به datetime تبدیل می‌کند.

    نکته مهم: اگر ورودی فقط تاریخ باشد (بدون ساعت)، برای کران پایین ابتدای
    روز و برای کران بالا انتهای روز گرفته می‌شود. وگرنه تراکنش‌های همان روز
    از بازه بیرون می‌افتند و خلاصه و بودجه اشتباه صفر می‌شوند.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        if end:
            return datetime(value.year, value.month, value.day, 23, 59, 59, 999999,
                            tzinfo=timezone.utc)
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        date_only = len(raw) <= 10 and "T" not in raw and " " not in raw
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            # شاید تاریخ شمسی است (1405/07/25). کاربر ایرانی ماه مالی‌اش
            # شمسی است و نباید مجبور شود خودش تبدیل کند.
            try:
                jd = parse_date(raw)
            except ValueError:
                raise HTTPException(400, f"bad datetime: {value}")
            if jd is None:
                raise HTTPException(400, f"bad datetime: {value}")
            if end:
                return datetime(jd.year, jd.month, jd.day, 23, 59, 59, 999999,
                                tzinfo=timezone.utc)
            return datetime(jd.year, jd.month, jd.day, tzinfo=timezone.utc)
        if date_only:
            if end:
                return d.replace(hour=23, minute=59, second=59, microsecond=999999,
                                 tzinfo=d.tzinfo or timezone.utc)
            return d.replace(hour=0, minute=0, second=0, microsecond=0,
                             tzinfo=d.tzinfo or timezone.utc)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    raise HTTPException(400, "occurred_at required")


def get_account(db: Session, user_id, account_id) -> FinAccount:
    """حساب را می‌گیرد و مالکیت را چک می‌کند. مرز امنیتی."""
    try:
        aid = uuid.UUID(str(account_id))
    except ValueError:
        raise HTTPException(400, "bad account_id")
    acc = db.execute(select(FinAccount).where(
        FinAccount.id == aid, FinAccount.user_id == user_id)).scalar_one_or_none()
    if acc is None:
        raise HTTPException(404, "account not found")
    return acc


def balance_of(db: Session, user_id, account_id=None) -> list[dict]:
    """موجودی حساب‌ها از جمع سطرها. هیچ ستون موجودی‌ای نگه‌داری نمی‌شود."""
    signed = func.sum(case(
        (FinEntry.direction == "debit", FinEntry.amount),
        else_=-FinEntry.amount,
    ))
    q = select(
        FinAccount.id, FinAccount.name, FinAccount.type, FinAccount.currency,
        FinAccount.opening_balance,
        func.coalesce(signed, 0),
    ).select_from(FinAccount).outerjoin(
        FinEntry, FinEntry.account_id == FinAccount.id
    ).where(FinAccount.user_id == user_id,
             # حساب‌های هزینه/درآمد داخلی حساب واقعی نیستند و در فهرست
             # موجودی کاربر نمایش داده نمی‌شوند.
             FinAccount.type.notin_(("income", "expense")))

    if account_id is not None:
        q = q.where(FinAccount.id == get_account(db, user_id, account_id).id)
    q = q.group_by(FinAccount.id, FinAccount.name, FinAccount.type,
                   FinAccount.currency, FinAccount.opening_balance)
    out = []
    for aid, name, typ, cur, opening, delta in db.execute(q).all():
        out.append({
            "id": str(aid), "name": name, "type": typ, "currency": cur,
            "balance": round(float(opening) + float(delta), 2),
        })
    return out


def log_transaction(db: Session, user_id, *, occurred_at, amount: float, direction: str,
                    account_id, counter_account_id=None, category_id=None,
                    description: str = "", counterparty: str | None = None,
                    source: str = "manual", external_ref: str | None = None,
                    is_transfer: bool = False, liability_id=None,
                    exclude_from_summary: bool | None = None,
                    token_id=None, actor: str = "agent") -> dict:
    """یک تراکنش متوازن می‌سازد: یک سطر روی حساب، یک سطر روی حساب مقابل.

    اگر counter_account_id ندهی، حساب مقابل بر اساس جهت و دسته انتخاب می‌شود:
    هزینه ← حساب هزینه پیش‌فرض، درآمد ← حساب درآمد پیش‌فرض.
    """
    if amount <= 0:
        raise HTTPException(400, "amount must be positive; use direction for sign")
    if direction not in ("debit", "credit"):
        raise HTTPException(400, "direction must be debit or credit")

    acc = get_account(db, user_id, account_id)

    if external_ref:
        dup = db.execute(select(FinTransaction).where(
            FinTransaction.user_id == user_id,
            FinTransaction.external_ref == external_ref)).scalar_one_or_none()
        if dup is not None:
            return {"ok": True, "duplicate": True, "transaction_id": str(dup.id),
                    "message": "already recorded"}

    if counter_account_id is None:
        want = "income" if direction == "credit" else "expense"
        # نام حساب مقابل نوع‌محور است، چون قید یکتایی روی (کاربر، نام) است.
        counter_name = COUNTER_ACCOUNT_NAMES[want]
        # اول حساب مقابل با همان نام پیش‌فرض را می‌جوییم. اگر قبلا ساخته شده
        # باشد نباید دوباره ساخته شود، وگرنه قید یکتایی (user_id, name) می‌شکند.
        counter = db.execute(select(FinAccount).where(
            FinAccount.user_id == user_id, FinAccount.name == counter_name,
            FinAccount.type == want).order_by(FinAccount.created_at)).scalars().first()
        if counter is None:
            counter = db.execute(select(FinAccount).where(
                FinAccount.user_id == user_id, FinAccount.type == want,
                FinAccount.active.is_(True)).order_by(FinAccount.created_at)).scalars().first()
        if counter is None:
            counter = FinAccount(user_id=user_id, name=counter_name, type=want)
            db.add(counter)
            try:
                db.flush()
            except IntegrityError:
                # مسابقه همزمان: دیگری ساخته است. همان را برمی‌داریم.
                db.rollback()
                counter = db.execute(select(FinAccount).where(
                    FinAccount.user_id == user_id, FinAccount.name == counter_name,
                    FinAccount.type == want)).scalars().first()
                if counter is None:
                    raise
    else:
        counter = get_account(db, user_id, counter_account_id)

    # اگر انتقال داخلی است، حتما حساب مقابل لازم است؛ وگرنه پول از حساب
    # خارج می‌شود و به جای دیگری نمی‌رود و موجودی غلط می‌شود.
    if is_transfer and counter_account_id is None:
        raise HTTPException(400, "transfer needs counter_account_id")

    if liability_id is not None:
        get_liability(db, user_id, liability_id)  # چک مالکیت

    # قاعده خودکار: دریافت اصل وام (credit روی حساب دارایی که به بدهی وصل است)
    # درآمد نیست، بدهی است. پس از خلاصه بیرون می‌رود. قسط‌ها (debit) هزینه
    # می‌مانند چون کاربر آن‌ها را در تفکیک دسته می‌خواهد.
    if exclude_from_summary is None:
        exclude_from_summary = bool(liability_id) and direction == "credit"

    tx = FinTransaction(
        user_id=user_id, occurred_at=_as_dt(occurred_at), description=description,
        category_id=category_id, counterparty=counterparty, source=source,
        external_ref=external_ref, is_transfer=is_transfer,
        liability_id=liability_id, exclude_from_summary=exclude_from_summary,
    )
    db.add(tx)
    db.flush()

    # دو سطر متوازن. جهت سطر دفتر معکوس جهت کاربر است:
    # پول از حساب خارج می‌شود (debit کاربر) ⇒ حساب اصلی بستانکار می‌شود.
    # این باعث می‌شود موجودی حساب و خلاصه درآمد/هزینه هر دو درست باشند.
    entry_dir = "credit" if direction == "debit" else "debit"
    db.add(FinEntry(transaction_id=tx.id, account_id=acc.id,
                    amount=amount, direction=entry_dir))
    db.add(FinEntry(transaction_id=tx.id, account_id=counter.id,
                    amount=amount, direction=direction))

    audit(db, user_id, "finance_transaction_log", {
        "amount": amount, "direction": direction, "account": acc.name,
        "counter_account": counter.name, "description": description,
        "external_ref": external_ref, "is_transfer": is_transfer,
        "liability_id": str(liability_id) if liability_id else None,
    }, token_id=token_id, actor=actor)
    db.commit()
    return {"ok": True, "duplicate": False, "transaction_id": str(tx.id),
            "amount": amount, "direction": direction, "account": acc.name}


_REAL_ACCOUNT_TYPES = ("asset", "liability")


def user_view(entries: list[tuple]) -> dict:
    """یک تراکنش دوسطری را از دید کاربر توصیف می‌کند.

    entries: [(direction, amount, account_type, account_name), ...]
    سطر حساب اصلی جهت معکوس جهت کاربر را دارد (log_transaction را ببین)، پس
    جهت کاربر از سطر روی حساب واقعی (دارایی/بدهی) خوانده می‌شود. اگر هر دو
    سطر واقعی باشند (انتقال)، حساب مبدا همان سطر بستانکار است.
    """
    real = [e for e in entries if e[2] in _REAL_ACCOUNT_TYPES]
    other = [e for e in entries if e[2] not in _REAL_ACCOUNT_TYPES]
    if len(real) >= 2:
        primary = next((e for e in real if e[0] == "credit"), real[0])
        counter = next((e for e in real if e is not primary), None)
    elif real:
        primary, counter = real[0], (other[0] if other else None)
    else:
        primary, counter = (entries[0] if entries else None), None
    if primary is None:
        return {"direction": None, "kind": None, "amount": 0.0,
                "account": None, "counter_account": None}
    direction = "debit" if primary[0] == "credit" else "credit"
    if counter is not None and counter[2] in ("income", "expense"):
        kind = counter[2]
    elif counter is not None and counter[2] in _REAL_ACCOUNT_TYPES:
        kind = "transfer"
    else:
        kind = "expense" if direction == "debit" else "income"
    return {"direction": direction, "kind": kind, "amount": float(primary[1]),
            "account": primary[3], "counter_account": counter[3] if counter else None}


def log_sms(db: Session, user_id, *, body: str, received_at=None, bank: str | None = None,
            parsed: dict | None = None, token_id=None) -> dict:
    """پیامک خام بانک را ذخیره می‌کند. اگر parsed بدهی، تراکنش هم می‌سازد.

    متن خام همیشه ذخیره می‌شود، حتی اگر پارس شکست بخورد. پس داده از دست نمی‌رود.
    """
    raw = FinRawMessage(user_id=user_id, channel="sms", bank=bank, body=body,
                        received_at=_as_dt(received_at) if received_at else datetime.now(timezone.utc))
    db.add(raw)
    db.flush()

    if not parsed:
        db.commit()
        return {"ok": True, "raw_message_id": str(raw.id), "parsed": False,
                "message": "stored raw; awaiting classification"}

    try:
        res = log_transaction(
            db, user_id,
            occurred_at=parsed.get("occurred_at") or received_at or datetime.now(timezone.utc),
            amount=float(parsed.get("amount", 0)),
            direction=parsed.get("direction", "debit"),
            account_id=parsed.get("account_id"),
            counter_account_id=parsed.get("counter_account_id"),
            category_id=parsed.get("category_id"),
            description=parsed.get("description") or body[:120],
            counterparty=parsed.get("counterparty"),
            source="sms",
            external_ref=parsed.get("external_ref"),
            token_id=token_id,
        )
    except HTTPException as e:
        raw.parse_error = str(e.detail)
        db.commit()
        return {"ok": False, "raw_message_id": str(raw.id), "parsed": False,
                "error": e.detail, "message": "raw stored but parse failed"}

    raw.parsed = True
    raw.transaction_id = uuid.UUID(res["transaction_id"])
    db.commit()
    return {"ok": True, "raw_message_id": str(raw.id),
            "transaction_id": res["transaction_id"],
            "duplicate": res.get("duplicate", False), "parsed": True}


def summary(db: Session, user_id, start, end) -> dict:
    """درآمد، هزینه، خالص و تفکیک دسته در بازه."""
    start_dt = _as_dt(start)
    end_dt = _as_dt(end, end=True)

    rows = db.execute(
        select(FinTransaction.id, FinTransaction.category_id,
               FinTransaction.description, FinTransaction.occurred_at,
               FinEntry.amount, FinEntry.direction, FinAccount.type)
        .select_from(FinTransaction)
        .join(FinEntry, FinEntry.transaction_id == FinTransaction.id)
        .join(FinAccount, FinAccount.id == FinEntry.account_id)
        .where(FinTransaction.user_id == user_id,
               FinTransaction.occurred_at >= start_dt,
               FinTransaction.occurred_at <= end_dt,
               FinTransaction.is_transfer.is_(False),
               FinTransaction.exclude_from_summary.is_(False))
    ).all()

    income = expense = 0.0
    by_cat: dict = {}
    cats = {c.id: c.name for c in db.execute(
        select(FinCategory).where(FinCategory.user_id == user_id)).scalars().all()}

    for _tid, cat_id, desc, _occ, amount, direction, acc_type in rows:
        amt = float(amount)
        if acc_type == "income" and direction == "credit":
            income += amt
        elif acc_type == "expense" and direction == "debit":
            expense += amt
            key = cats.get(cat_id, "بدون دسته")
            by_cat[key] = by_cat.get(key, 0) + amt

    # انتقال بین حساب‌های خود کاربر هزینه نیست، پس از جمع بیرون می‌ماند.
    # (فیلتر در کوئری بالا اعمال شده، اینجا فقط برای شفافیت گزارش است.)
    return {
        "from": start_dt.date().isoformat(), "to": end_dt.date().isoformat(),
        "from_jalali": to_jalali_str(start_dt.date()),
        "to_jalali": to_jalali_str(end_dt.date()),
        "income": round(income, 2), "expense": round(expense, 2),
        "net": round(income - expense, 2),
        "by_category": [{"category": k, "amount": round(v, 2)}
                        for k, v in sorted(by_cat.items(), key=lambda x: -x[1])],
    }


def cashflow(db: Session, user_id, months: int = 6, today: date | None = None) -> list[dict]:
    """درآمد و هزینه هر ماه شمسی، از قدیم به جدید. ماه جاری تا امروز است."""
    cur = today or date.today()
    out = []
    for _ in range(max(1, min(months, 24))):
        start, end = month_bounds_jalali(cur)
        s = summary(db, user_id, start, min(end, today or date.today()))
        jy, jm, _jd = gregorian_to_jalali(start)
        out.append({"month": f"{jy:04d}/{jm:02d}", "from": start.isoformat(),
                    "income": s["income"], "expense": s["expense"], "net": s["net"]})
        cur = start - timedelta(days=1)
    return list(reversed(out))


def budget_status(db: Session, user_id, start, end) -> list[dict]:
    """بودجه هر دسته در برابر واقعی."""
    budgets = db.execute(select(FinBudget).where(
        FinBudget.user_id == user_id, FinBudget.active.is_(True))).scalars().all()
    cats = {c.id: c.name for c in db.execute(
        select(FinCategory).where(FinCategory.user_id == user_id)).scalars().all()}
    out = []
    for b in budgets:
        # مصرف بودجه = جمع سطرهای روی حساب‌های نوع expense. فیلتر روی نوع
        # حساب درست است، نه روی جهت سطر، چون جهت سطر بسته به نوع حساب معنا
        # پیدا می‌کند و با تغییر منطق دفتر نباید بودجه بشکند.
        spent = db.execute(
            select(func.coalesce(func.sum(FinEntry.amount), 0))
            .select_from(FinEntry)
            .join(FinTransaction, FinTransaction.id == FinEntry.transaction_id)
            .join(FinAccount, FinAccount.id == FinEntry.account_id)
            .where(FinTransaction.user_id == user_id,
                   FinTransaction.category_id == b.category_id,
                   FinTransaction.occurred_at >= _as_dt(start),
                   FinTransaction.occurred_at <= _as_dt(end, end=True),
                   FinTransaction.is_transfer.is_(False),
                   FinTransaction.exclude_from_summary.is_(False),
                   FinAccount.type == "expense")
        ).scalar_one()
        limit = float(b.amount)
        used = float(spent)
        out.append({
            "category": cats.get(b.category_id, "?"), "period": b.period,
            "budget": round(limit, 2), "spent": round(used, 2),
            "remaining": round(limit - used, 2),
            "over": used > limit,
            "pct": round((used / limit * 100) if limit else 0, 1),
        })
    return out


# ---------- بدهی و تعهد ----------

def get_liability(db: Session, user_id, liability_id) -> FinLiability:
    """بدهی را می‌گیرد و مالکیت را چک می‌کند. مرز امنیتی."""
    try:
        lid = uuid.UUID(str(liability_id))
    except (ValueError, AttributeError):
        raise HTTPException(400, "bad liability_id")
    row = db.execute(select(FinLiability).where(
        FinLiability.id == lid, FinLiability.user_id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "liability not found")
    return row


def _next_due(liab: FinLiability, paid_count: int) -> date | None:
    """سررسید بعدی در تقویم شمسی محاسبه می‌شود.

    چرا: کاربر ایرانی قسط را با روز ماه شمسی می‌شناسد (مثلا ۱۶ هر ماه
    شمسی). اگر روز را روی ماه میلادی اعمال کنیم، سررسید چند روز جابه‌جا
    می‌شود و یادآوری دیرکرد اشتباه می‌دهد.
    """
    if liab.status == "settled":
        return None
    if liab.installments_total and paid_count >= liab.installments_total:
        return None
    jy, jm, jd = gregorian_to_jalali(liab.start_date)
    day = liab.due_day or jd
    today = date.today()
    for _ in range(600):
        # روز معتبر در ماه شمسی (۱ تا ۶ سی‌ویک روز، ۷ تا ۱۱ سی روز، اسفند ۲۹/۳۰)
        if jm <= 6:
            last = 31
        elif jm <= 11:
            last = 30
        else:
            nxt = jalali_to_gregorian(jy + 1, 1, 1)
            last = (nxt - timedelta(days=1)).day
        cand = jalali_to_gregorian(jy, jm, min(day, last))
        if cand >= today:
            return cand
        jm += 1
        if jm > 12:
            jm = 1
            jy += 1
    return None


def liability_view(db: Session, user_id, liab: FinLiability) -> dict:
    """نمای یک بدهی: پرداخت‌شده، مانده، تعداد قسط پرداخت‌شده، سررسید بعدی."""
    paid = db.execute(
        select(func.coalesce(func.sum(FinEntry.amount), 0))
        .select_from(FinEntry)
        .join(FinTransaction, FinTransaction.id == FinEntry.transaction_id)
        .join(FinAccount, FinAccount.id == FinEntry.account_id)
        .where(FinTransaction.user_id == user_id,
               FinTransaction.liability_id == liab.id,
               FinAccount.type == "expense",
               FinEntry.direction == "debit")
    ).scalar_one()
    paid = float(paid)
    principal = float(liab.principal)
    remaining = max(principal - paid, 0.0)
    per = float(liab.installment_amount)
    paid_count = int(round(paid / per)) if per > 0 else 0
    nxt = _next_due(liab, paid_count)
    return {
        "id": str(liab.id), "name": liab.name, "kind": liab.kind,
        "principal": round(principal, 2), "paid": round(paid, 2),
        "remaining": round(remaining, 2),
        "installments_total": liab.installments_total,
        "installments_paid": paid_count,
        "installment_amount": round(per, 2),
        "interest_rate": float(liab.interest_rate),
        "start_date": liab.start_date.isoformat(),
        "start_date_jalali": to_jalali_str(liab.start_date),
        "next_due": nxt.isoformat() if nxt else None,
        "next_due_jalali": to_jalali_str(nxt) if nxt else None,
        "status": liab.status,
        "account_id": str(liab.account_id) if liab.account_id else None,
        "note": liab.note,
    }


def liabilities_list(db: Session, user_id, status: str | None = None) -> dict:
    q = select(FinLiability).where(FinLiability.user_id == user_id)
    if status:
        q = q.where(FinLiability.status == status)
    rows = db.execute(q.order_by(FinLiability.created_at)).scalars().all()
    items = [liability_view(db, user_id, r) for r in rows]
    total_remaining = sum(i["remaining"] for i in items if i["status"] == "active")
    return {"liabilities": items, "total_remaining": round(total_remaining, 2)}


def liability_create(db: Session, user_id, *, name: str, principal: float,
                     installments_total: int = 0, installment_amount: float = 0,
                     interest_rate: float = 0, start_date=None, due_day=None,
                     account_id=None, kind: str = "loan", note: str | None = None,
                     token_id=None, actor: str = "agent") -> dict:
    """ثبت بدهی. اصل وام اینجا بدهی است، نه درآمد."""
    if principal < 0:
        raise HTTPException(400, "principal must be >= 0")
    sd = parse_date(start_date) if start_date else date.today()
    if sd is None:
        sd = date.today()
    if account_id is not None:
        get_account(db, user_id, account_id)
    row = FinLiability(
        user_id=user_id, name=name, kind=kind, principal=principal,
        interest_rate=interest_rate, installments_total=installments_total,
        installment_amount=installment_amount, start_date=sd,
        due_day=due_day or sd.day, account_id=account_id, note=note,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "liability with this name already exists")
    audit(db, user_id, "finance_liability_create", {
        "name": name, "principal": principal,
        "installments_total": installments_total,
    }, token_id=token_id, actor=actor)
    db.commit()
    return {"ok": True, "liability": liability_view(db, user_id, row)}


def liability_update(db: Session, user_id, liability_id, *,
                     name=None, principal=None, installments_total=None,
                     installment_amount=None, interest_rate=None,
                     due_day=None, status=None, note=None,
                     token_id=None, actor: str = "agent") -> dict:
    row = get_liability(db, user_id, liability_id)
    changed = {}
    for key, val in (("name", name), ("principal", principal),
                     ("installments_total", installments_total),
                     ("installment_amount", installment_amount),
                     ("interest_rate", interest_rate), ("due_day", due_day),
                     ("status", status), ("note", note)):
        if val is not None:
            setattr(row, key, val)
            changed[key] = val
    if status == "settled":
        row.status = "settled"
    audit(db, user_id, "finance_liability_update",
          {"id": str(row.id), **changed}, token_id=token_id, actor=actor)
    db.commit()
    return {"ok": True, "liability": liability_view(db, user_id, row)}


# ---------- دسته‌های پیش‌فرض ----------

DEFAULT_EXPENSE_CATEGORIES = [
    "خوراک و سوپرمارکت",
    "حمل‌ونقل و سوخت",
    "قبوض",
    "سلامت و درمان",
    "آموزش",
    "تفریح",
    "هدیه و مناسبت",
    "مالیات و عوارض",
    "خرید روزمره",
    "بازسازی خانه",
    "قسط مسکن",
    "قسط ازدواج",
    "قسط رسالت",
    "قرض دادن",
]

DEFAULT_INCOME_CATEGORIES = ["حقوق", "درآمد دیگر"]


def ensure_default_categories(db: Session, user_id, commit: bool = True) -> int:
    """دسته‌های پرکاربرد فارسی را برای کاربر می‌سازد.

    idempotent است: اگر دسته‌ای با همان نام و نوع باشد، دوباره ساخته نمی‌شود.
    در ثبت‌نام کاربر جدید صدا زده می‌شود تا از روز اول دسته داشته باشد.
    """
    existing = {(c.name, c.kind) for c in db.execute(
        select(FinCategory).where(FinCategory.user_id == user_id)).scalars().all()}
    added = 0
    for name in DEFAULT_EXPENSE_CATEGORIES:
        if (name, "expense") not in existing:
            db.add(FinCategory(user_id=user_id, name=name, kind="expense"))
            added += 1
    for name in DEFAULT_INCOME_CATEGORIES:
        if (name, "income") not in existing:
            db.add(FinCategory(user_id=user_id, name=name, kind="income"))
            added += 1
    if commit:
        db.commit()
    return added
