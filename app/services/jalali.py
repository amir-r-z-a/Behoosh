"""تبدیل تاریخ شمسی و میلادی بدون وابستگی بیرونی.

کاربر ایرانی ماه مالی‌اش شمسی است. اگر ورودی شمسی بدهد و ما آن را میلادی
تفسیر کنیم، گزارش یک ماه جابه‌جا می‌شود. پس هر ورودی تاریخ از دو قالب
پذیرفته می‌شود: ISO میلادی (2026-10-17) و شمسی (1405/07/25 یا 1405-07-25).
"""
from datetime import date, datetime

_MONTH_DAYS = [0, 31, 29 if False else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap_gregorian(gy: int) -> bool:
    return (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """الگوریتم استاندارد تبدیل شمسی به میلادی."""
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
    month_days = [0, 31, 29 if _is_leap_gregorian(gy) else 28, 31, 30, 31, 30,
                  31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return date(gy, gm, gd)


def gregorian_to_jalali(g: date) -> tuple[int, int, int]:
    """تبدیل میلادی به شمسی، برای نمایش در گزارش."""
    gy, gm, gd = g.year, g.month, g.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2] + gd2
    if gm > 2 and _is_leap_gregorian(gy):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def parse_date(value) -> date | None:
    """هر ورودی تاریخ را به date میلادی تبدیل می‌کند.

    شمسی تشخیص داده می‌شود اگر سال بزرگ‌تر از ۱۷۰۰ نباشد. میلادی همیشه
    سال چهاررقمی بزرگ دارد، پس تشخیص بی‌ابهام است.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    # جداکننده‌ها: / - .
    norm = raw.replace("/", "-").replace(".", "-")
    head = norm.split("T")[0].split(" ")[0]
    parts = head.split("-")
    if len(parts) != 3:
        raise ValueError(f"bad date: {value}")
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(f"bad date: {value}")
    if y < 1700:
        if not (1 <= m <= 12 and 1 <= d <= 31):
            raise ValueError(f"bad jalali date: {value}")
        return jalali_to_gregorian(y, m, d)
    return date(y, m, d)


def to_jalali_str(g: date) -> str:
    jy, jm, jd = gregorian_to_jalali(g)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def month_bounds_jalali(g: date) -> tuple[date, date]:
    """اول و آخر ماه شمسی که تاریخ داده‌شده در آن است."""
    jy, jm, _jd = gregorian_to_jalali(g)
    start = jalali_to_gregorian(jy, jm, 1)
    if jm <= 6:
        end = jalali_to_gregorian(jy, jm, 31)
    elif jm <= 11:
        end = jalali_to_gregorian(jy, jm, 30)
    else:
        # اسفند: با آزمون سال بعد تعیین می‌شود (کبیسه یا نه)
        end = jalali_to_gregorian(jy + 1, 1, 1)
        from datetime import timedelta
        end = end - timedelta(days=1)
    return start, end
