"""موتور مزاج دو محوره بهوش.

مدل: هر قلم غذا یک بردار (cold_warm, dry_wet) در بازه -1..1 دارد.
  cold_warm: منفی = سرد، مثبت = گرم
  dry_wet:   منفی = تر،  مثبت = خشک

دو عدد تولید می‌شود:
  1) بردار امروز  = میانگین وزنی برداری اقلام امروز (وزن = مقدار مؤثر اشباع‌شده)
  2) بردار حالت   = مجموع نمایی روزهای گذشته + امروز (با ضریب فراموشی)

هشدار صادقانه: این یک چارچوب تصمیم‌یار است، نه تشخیص پزشکی و نه ادعای
اعتبار بالینی. بردارهای پایه باید منبع‌دار و بازبینی‌شده باشند
(ستون temperament_vectors.source_ref / verified).
"""
from __future__ import annotations

import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Meal, TemperamentState, TemperamentVector

# ضریب فراموشی روزانه: سهم هر روز گذشته نسبت به روز بعدش
DECAY = 0.6
# مقدار مرجع اشباع وزن (گرم/واحد) — از این بیشتر اثر افزوده‌ی کم دارد
SATURATION = 250.0


def _effective_weight(quantity: float, unit: str) -> float:
    """تبدیل مقدار به وزن مؤثر با اشباع لگاریتمی (ضد سوگیری مقدار بزرگ)."""
    q = max(float(quantity or 0), 0.0)
    if q <= 0:
        return 0.0
    return math.log1p(q) / math.log1p(SATURATION)


def _item_vector(item_name: str, db: Session) -> tuple[float, float] | None:
    """بردار پایه یک قلم غذا از جدول مرجع. اگر نبود، None."""
    row = db.execute(
        select(TemperamentVector).where(
            TemperamentVector.item_name == item_name,
            TemperamentVector.item_type == "food",
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return float(row.cold_warm), float(row.dry_wet)


def day_vector(db: Session, user_id, d: date) -> tuple[float, float, int]:
    """بردار مزاج اقلام یک روز. برمی‌گرداند (cold_warm, dry_wet, n_items)."""
    rows = db.execute(
        select(Meal).where(Meal.user_id == user_id, Meal.log_date == d)
    ).scalars().all()
    if not rows:
        return 0.0, 0.0, 0

    num_cw = num_dw = den = 0.0
    n = 0
    for m in rows:
        # اولویت: بردار ذخیره‌شده روی خود ردیف؛ وگرنه از جدول مرجع
        cw, dw = float(m.cold_warm or 0), float(m.dry_wet or 0)
        if cw == 0 and dw == 0:
            vec = _item_vector(m.item_name, db)
            if vec:
                cw, dw = vec
        w = _effective_weight(m.quantity, m.unit)
        if w <= 0:
            w = 0.1  # قلم بدون مقدار هم اثر نمادین دارد
        num_cw += cw * w
        num_dw += dw * w
        den += w
        n += 1
    if den <= 0:
        return 0.0, 0.0, n
    return num_cw / den, num_dw / den, n


def state_vector(db: Session, user_id, d: date, window: int = 14) -> tuple[float, float]:
    """بردار حالت تجمعی با فراموشی نمایی روی پنجره روزهای گذشته."""
    num_cw = num_dw = den = 0.0
    for i in range(window):
        dd = date.fromordinal(d.toordinal() - i)
        cw, dw, n = day_vector(db, user_id, dd)
        if n == 0:
            continue
        w = DECAY ** i
        num_cw += cw * w
        num_dw += dw * w
        den += w
    if den <= 0:
        return 0.0, 0.0
    return num_cw / den, num_dw / den


def label(cw: float, dw: float) -> str:
    """برچسب انسانی برای یک بردار."""
    def ax(v, neg, pos, mid):
        if v <= -0.15:
            return neg
        if v >= 0.15:
            return pos
        return mid
    return f"{ax(cw, 'سرد', 'گرم', 'معتدل')} و {ax(dw, 'تر', 'خشک', 'معتدل')}"


def compute_and_store(db: Session, user_id, d: date) -> dict:
    """محاسبه و ذخیره بردار حالت روز. برای idempotent بودن upsert می‌کند."""
    cw, dw = state_vector(db, user_id, d)
    row = db.execute(
        select(TemperamentState).where(
            TemperamentState.user_id == user_id, TemperamentState.log_date == d
        )
    ).scalar_one_or_none()
    if row is None:
        row = TemperamentState(user_id=user_id, log_date=d)
        db.add(row)
    row.cold_warm, row.dry_wet = round(cw, 3), round(dw, 3)
    db.commit()
    return {"cold_warm": round(cw, 3), "dry_wet": round(dw, 3), "label": label(cw, dw)}
