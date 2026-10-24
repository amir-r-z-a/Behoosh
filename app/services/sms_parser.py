"""پارسر پیامک بانکی ایران.

پیامک بانک پرکاربردترین راه ورود داده مالی در ایران است. متن خام همیشه ذخیره
می‌شود و این پارسر فقط تلاش می‌کند از آن یک تراکنش بسازد. اگر مطمئن نبود،
هیچ تراکنشی نمی‌سازد و متن خام برای بازبینی می‌ماند. هیچ‌وقت حدس نمی‌زند.

دو تصمیم مهم:
۱. واحد پول: بانک‌های ایران مبلغ را ریال می‌نویسند ولی کاربر تومان فکر می‌کند.
   پس ریال به تومان تبدیل می‌شود (تقسیم بر ۱۰) و واحد اصلی هم در خروجی
   نگه داشته می‌شود تا قابل حسابرسی باشد.
۲. تاریخ: اگر تاریخ شمسی در متن باشد به میلادی تبدیل می‌شود، چون دیتابیس
   میلادی ذخیره می‌کند.
"""
import re
from datetime import datetime, timezone

# ارقام فارسی و عربی به لاتین
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# جداکننده هزارگان در متن فارسی: ویرگول لاتین، ویرگول فارسی، ممیز عربی
_SEP = re.compile(r"[,\u060C\u066C\u066B\u066B\s\u200c]")

_AMOUNT = re.compile(
    r"(?:مبلغ|به\s*مبلغ|مبلغی\s*معادل)\s*:?\s*([0-9][0-9,\u060C\u066C\u066B\.]*)"
)
_AMOUNT_ANY = re.compile(
    r"([0-9][0-9,\u060C\u066C\u066B\.]*)\s*(ریال|تومان)"
)
_BALANCE = re.compile(
    r"(?:مانده|موجودی)\s*:?\s*([0-9][0-9,\u060C\u066C\u066B\.]*)"
)
_CARD = re.compile(r"(?:\*{4,}|کارت|حساب)[^0-9]{0,25}([0-9]{4})\b")
_REF = re.compile(r"(?:پیگیری|مرجع|شماره\s*پیگیری|کد\s*پیگیری)\s*:?\s*([0-9]{4,})")
_JALALI = re.compile(r"(1[34][0-9]{2})/([0-9]{1,2})/([0-9]{1,2})")

_DEBIT = ("کسر", "برداشت", "پرداخت", "خرید", "بدهکار", "کاهش", "انتقال از",
          "از حساب شما")
_CREDIT = ("واریز", "افزایش", "بستانکار", "به حساب شما", "دریافت", "به حساب")


def _num(raw: str) -> float:
    """عدد فارسی/لاتین با جداکننده را به عدد اعشاری تبدیل می‌کند."""
    cleaned = _SEP.sub("", raw.translate(_DIGITS))
    if cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    return float(cleaned)


def _jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ شمسی به میلادی. الگوریتم استاندارد jalaali."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    months = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return gy, gm, gd


def parse_sms(body: str) -> dict | None:
    """از متن پیامک بانک یک dict تراکنش می‌سازد، یا None اگر مطمئن نبود.

    خروجی: amount (تومان)، direction، unit اصلی، card_last4، balance،
    occurred_at، external_ref، description.
    """
    if not body or not body.strip():
        return None
    text = body.translate(_DIGITS)

    # اول مبلغی که با کلمه «مبلغ» علامت خورده. وگرنه اولین عددی که واحد
    # پول دارد. عددهای مربوط به «مانده/موجودی» کنار گذاشته می‌شوند تا
    # موجودی به‌جای مبلغ تراکنش برداشته نشود.
    m = _AMOUNT.search(text)
    unit = None
    if m:
        raw_amount = _num(m.group(1))
        tail = text[m.end():m.end() + 25]
        if "تومان" in tail:
            unit = "toman"
        elif "ریال" in tail:
            unit = "rial"
        elif "ریال" in text:
            unit = "rial"
        elif "تومان" in text:
            unit = "toman"
    else:
        raw_amount = None

    if raw_amount is None or unit is None:
        for cand in _AMOUNT_ANY.finditer(text):
            before = text[max(0, cand.start() - 12):cand.start()]
            if "مانده" in before or "موجودی" in before:
                continue
            raw_amount = _num(cand.group(1))
            unit = "toman" if cand.group(2) == "تومان" else "rial"
            break

    if raw_amount is None or unit is None or raw_amount <= 0:
        return None

    amount = raw_amount if unit == "toman" else raw_amount / 10

    debit_hits = sum(1 for k in _DEBIT if k in text)
    credit_hits = sum(1 for k in _CREDIT if k in text)
    if debit_hits == 0 and credit_hits == 0:
        return None
    if debit_hits == credit_hits:
        return None
    direction = "debit" if debit_hits > credit_hits else "credit"

    out: dict = {
        "amount": round(amount, 2),
        "direction": direction,
        "unit": unit,
        "raw_amount": raw_amount,
        "description": body.strip()[:200],
    }

    c = _CARD.search(text)
    if c:
        out["card_last4"] = c.group(1)

    b = _BALANCE.search(text)
    if b:
        bal = _num(b.group(1))
        out["balance"] = round(bal / 10 if unit == "rial" else bal, 2)

    r = _REF.search(text)
    if r:
        out["external_ref"] = f"sms:{r.group(1)}"

    j = _JALALI.search(text)
    if j:
        try:
            gy, gm, gd = _jalali_to_gregorian(int(j.group(1)), int(j.group(2)), int(j.group(3)))
            out["occurred_at"] = datetime(gy, gm, gd, tzinfo=timezone.utc).isoformat()
        except Exception:
            pass

    return out
