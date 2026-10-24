"""محاسبه جمع روز. هر نوشتن باید این را برگرداند تا کاربر بازخورد فوری ببیند."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    Habit, Meal, MoodLog, Prayer, ScreenTime, SleepLog, Workout,
)


def day_summary(db: Session, user_id, d: date) -> dict:
    s = get_settings()

    kcal, prot, carb, fat = db.execute(
        select(
            func.coalesce(func.sum(Meal.kcal), 0),
            func.coalesce(func.sum(Meal.protein_g), 0),
            func.coalesce(func.sum(Meal.carbs_g), 0),
            func.coalesce(func.sum(Meal.fat_g), 0),
        ).where(Meal.user_id == user_id, Meal.log_date == d)
    ).one()

    sleep = db.execute(
        select(SleepLog).where(SleepLog.user_id == user_id, SleepLog.log_date == d)
    ).scalar_one_or_none()

    wmin = db.execute(
        select(func.coalesce(func.sum(Workout.duration_min), 0))
        .where(Workout.user_id == user_id, Workout.log_date == d)
    ).scalar_one()

    pdone = db.execute(
        select(func.count()).select_from(Prayer)
        .where(Prayer.user_id == user_id, Prayer.log_date == d, Prayer.status == "done")
    ).scalar_one()

    mood = db.execute(
        select(MoodLog).where(MoodLog.user_id == user_id, MoodLog.log_date == d)
    ).scalar_one_or_none()

    scr = db.execute(
        select(ScreenTime).where(ScreenTime.user_id == user_id, ScreenTime.log_date == d)
    ).scalar_one_or_none()

    hab = db.execute(
        select(Habit).where(Habit.user_id == user_id, Habit.log_date == d)
    ).scalar_one_or_none()

    # مزاج دو محوره روز
    temp = {"cold_warm": 0.0, "dry_wet": 0.0, "label": "بدون داده"}
    try:
        from app.temperament import day_vector, label
        cw, dw, n_items = day_vector(db, user_id, d)
        if n_items:
            temp = {"cold_warm": round(cw, 3), "dry_wet": round(dw, 3),
                    "label": label(cw, dw), "items": n_items}
    except Exception:
        pass

    kcal_f, prot_f = float(kcal), float(prot)
    data = {
        "log_date": d,
        "kcal": kcal_f,
        "protein_g": prot_f,
        "carbs_g": float(carb),
        "fat_g": float(fat),
        "kcal_target": s.default_kcal_target,
        "protein_target": s.default_protein_target,
        "kcal_remaining": max(s.default_kcal_target - kcal_f, 0),
        "protein_remaining": max(s.default_protein_target - prot_f, 0),
        "sleep_hours": float(sleep.main_hours) if sleep else 0,
        "sleep_quality": int(sleep.quality) if sleep else 0,
        "workout_min": int(wmin),
        "prayers_done": int(pdone),
        "mood": int(mood.mood) if mood else 0,
        "stress": int(mood.stress) if mood else 0,
        "energy": int(mood.energy) if mood else 0,
        "screen_total_min": int(scr.total_min) if scr else 0,
        "screen_instagram_min": int(scr.instagram_min) if scr else 0,
        "water_liters": float(hab.water_liters) if hab else 0,
        "breathing_done": bool(hab.breathing_done) if hab else False,
        "temperament": temp,
    }
    tmsg = f"مزاج روز: {temp['label']}." if temp.get("items") else ""
    data["message"] = (
        f"ثبت شد. کالری {kcal_f:.0f} از {s.default_kcal_target:.0f} "
        f"({data['kcal_remaining']:.0f} باقی‌مانده)، "
        f"پروتئین {prot_f:.0f} از {s.default_protein_target:.0f} گرم، "
        f"خواب {data['sleep_hours']:.1f} ساعت، "
        f"نماز {data['prayers_done']} از ۵. {tmsg}"
    ).strip()
    return data
