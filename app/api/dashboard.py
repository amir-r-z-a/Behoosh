"""اندپوینت جامع داشبورد: همه داده لازم برای رندر یکجا."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_deps import (
    SCOPE_HEALTH_READ, Principal, require_scope,
)
from app.core.config import get_settings
from app.db.models import (
    BodyMetric, Habit, Meal, MoodLog, Prayer, ScreenTime, SleepLog, Workout,
)
from app.db.session import get_db

router = APIRouter(prefix="/v1", tags=["dashboard"])

PRAYERS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]




def _series(db: Session, uid, model, date_col, val_col, start, agg="sum"):
    fn = func.sum(val_col) if agg == "sum" else func.avg(val_col)
    rows = db.execute(
        select(date_col, fn).where(model.user_id == uid, date_col >= start)
        .group_by(date_col).order_by(date_col)).all()
    return {d.isoformat(): float(v or 0) for d, v in rows}


@router.get("/dashboard")
def dashboard(days: int = 30,
              p: Principal = Depends(require_scope(SCOPE_HEALTH_READ)),
              db: Session = Depends(get_db)):
    # قاعده طلایی: هویت فقط از توکن. هیچ‌وقت از دیتابیس خوانده نمی‌شود.
    uid = p.user_id
    s = get_settings()
    today = date.today()
    start = today - timedelta(days=days - 1)

    days_list = [(start + timedelta(days=i)).isoformat() for i in range(days)]

    kcal = _series(db, uid, Meal, Meal.log_date, Meal.kcal, start)
    prot = _series(db, uid, Meal, Meal.log_date, Meal.protein_g, start)
    carbs = _series(db, uid, Meal, Meal.log_date, Meal.carbs_g, start)
    fat = _series(db, uid, Meal, Meal.log_date, Meal.fat_g, start)
    slh = _series(db, uid, SleepLog, SleepLog.log_date, SleepLog.main_hours, start, "avg")
    slq = _series(db, uid, SleepLog, SleepLog.log_date, SleepLog.quality, start, "avg")
    wmin = _series(db, uid, Workout, Workout.log_date, Workout.duration_min, start)
    wkcal = _series(db, uid, Workout, Workout.log_date, Workout.kcal_burned, start)
    mood = _series(db, uid, MoodLog, MoodLog.log_date, MoodLog.mood, start, "avg")
    stress = _series(db, uid, MoodLog, MoodLog.log_date, MoodLog.stress, start, "avg")
    energy = _series(db, uid, MoodLog, MoodLog.log_date, MoodLog.energy, start, "avg")
    scr_t = _series(db, uid, ScreenTime, ScreenTime.log_date, ScreenTime.total_min, start)
    scr_i = _series(db, uid, ScreenTime, ScreenTime.log_date, ScreenTime.instagram_min, start)
    scr_g = _series(db, uid, ScreenTime, ScreenTime.log_date, ScreenTime.telegram_min, start)
    unlocks = _series(db, uid, ScreenTime, ScreenTime.log_date, ScreenTime.unlocks, start)
    notif = _series(db, uid, ScreenTime, ScreenTime.log_date, ScreenTime.notifications, start)
    water = _series(db, uid, Habit, Habit.log_date, Habit.water_liters, start, "avg")

    # نماز: تعداد انجام‌شده در روز
    prows = db.execute(
        select(Prayer.log_date, func.count()).where(
            Prayer.user_id == uid, Prayer.log_date >= start,
            Prayer.status == "done").group_by(Prayer.log_date)).all()
    pray_done = {d.isoformat(): int(c) for d, c in prows}

    # بدن
    brows = db.execute(
        select(BodyMetric).where(BodyMetric.user_id == uid)
        .order_by(BodyMetric.measured_at.desc()).limit(12)).scalars().all()
    body = [{"d": b.measured_at.isoformat(), "weight_kg": b.weight_kg,
             "body_fat_pct": b.body_fat_pct, "visceral_fat": b.visceral_fat,
             "muscle_kg": b.muscle_kg, "muscle_pct": b.muscle_pct,
             "water_pct": b.water_pct, "bmi": b.bmi} for b in brows]

    # آخرین تمرین هر عضله (روز پیش)
    wrows = db.execute(
        select(Workout.log_date, Workout.muscles, Workout.kind, Workout.notes)
        .where(Workout.user_id == uid).order_by(Workout.log_date.desc())).all()
    muscle_last = {}
    for d_, muscles, kind, notes in wrows:
        for m in (muscles or []):
            if m not in muscle_last:
                muscle_last[m] = {"days_ago": (today - d_).days, "kind": kind,
                                  "notes": notes}

    # حجم تمرین هر عضله (تعداد ست کل)
    muscle_vol = {}
    for _, muscles, _, _ in wrows:
        for m in (muscles or []):
            muscle_vol[m] = muscle_vol.get(m, 0) + 1

    # مزاج دو محوره: بردار روزانه + بردار اقلام امروز
    from app.db.models import (TemperamentExam, TemperamentProfile,
                               TemperamentVector)
    from app.temperament import day_vector, label as tlabel
    # بردار حالت هر روز را از خود وعده‌ها محاسبه کن (جدول حالت ممکن است خالی باشد)
    from app.temperament import state_vector as _state_vec
    temp_cw, temp_dw = [], []
    for x in days_list:
        dd = date.fromisoformat(x)
        cw, dw = _state_vec(db, uid, dd)
        temp_cw.append(round(cw, 3))
        temp_dw.append(round(dw, 3))

    # اقلام امروز با بردار
    tday = today
    mrows = db.execute(
        select(Meal).where(Meal.user_id == uid, Meal.log_date == tday)).scalars().all()
    items = []
    for m in mrows:
        cw, dw = float(m.cold_warm or 0), float(m.dry_wet or 0)
        src = "ثبت‌شده"
        if cw == 0 and dw == 0:
            v = db.execute(select(TemperamentVector).where(
                TemperamentVector.item_name == m.item_name,
                TemperamentVector.item_type == "food")).scalar_one_or_none()
            if v:
                cw, dw = float(v.cold_warm), float(v.dry_wet)
                src = "پایه" if v.verified else "پایه (تأییدنشده)"
        items.append({"name": m.item_name, "slot": m.slot,
                      "quantity": float(m.quantity), "unit": m.unit,
                      "cold_warm": round(cw, 2), "dry_wet": round(dw, 2),
                      "source": src})
    dcw, ddw, ditems = day_vector(db, uid, tday)
    prof = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    base = {"cold_warm": float(prof.base_cold_warm) if prof else 0,
            "dry_wet": float(prof.base_dry_wet) if prof else 0,
            "constitution": prof.constitution if prof else None,
            "set": bool(prof)}
    exrows = db.execute(select(TemperamentExam).where(
        TemperamentExam.user_id == uid).order_by(TemperamentExam.organ)).scalars().all()
    exam = [{"organ": r.organ, "cold_warm": float(r.cold_warm),
             "dry_wet": float(r.dry_wet), "severity": r.severity,
             "finding": r.finding} for r in exrows]
    temperament = {
        "today": {"cold_warm": round(dcw, 3), "dry_wet": round(ddw, 3),
                   "label": tlabel(dcw, ddw) if ditems else "بدون داده",
                   "items": ditems},
        "items": items,
        "base": base,
        "exam": exam,
    }

    def fill(d):
        return [d.get(x) or 0 for x in days_list]

    return {
        "days": days_list,
        "targets": {"kcal": s.default_kcal_target,
                    "protein_g": s.default_protein_target,
                    "sleep_hours": s.default_sleep_target,
                    "screen_total_min": s.default_screen_target_min,
                    "screen_instagram_min": s.default_instagram_target_min},
        "kcal": fill(kcal), "protein": fill(prot),
        "carbs": fill(carbs), "fat": fill(fat),
        "sleep_hours": fill(slh), "sleep_quality": fill(slq),
        "workout_min": fill(wmin), "workout_kcal": fill(wkcal),
        "mood": fill(mood), "stress": fill(stress), "energy": fill(energy),
        "screen_total": fill(scr_t), "screen_instagram": fill(scr_i),
        "screen_telegram": fill(scr_g),
        "unlocks": fill(unlocks), "notifications": fill(notif),
        "water": fill(water), "prayers_done": fill(pray_done),
        "body": body,
        "muscle_last": muscle_last,
        "muscle_volume": muscle_vol,
        "temp_cold_warm": temp_cw,
        "temp_dry_wet": temp_dw,
        "temperament": temperament,
    }
