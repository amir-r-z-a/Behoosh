"""ثبت روزانه سلامت: غذا، خواب، ورزش، بدن، نماز، حال، اسکرین‌تایم، عادت."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as S
from app.api.auth_deps import Principal
from app.api.health._common import HEALTH_READ, HEALTH_WRITE, _parse_dt, _uid
from app.api.summary import day_summary
from app.core.config import get_settings
from app.db.models import (
    BodyMetric, Habit, Meal, MoodLog, Prayer, ScreenTime, SleepLog, Workout, WorkoutSet,
)
from app.db.session import get_db

router = APIRouter()


@router.post("/log_meal")
def log_meal(payload: S.MealIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    for it in payload.items:
        db.add(Meal(
            user_id=uid, log_date=payload.log_date, slot=payload.slot,
            item_name=it.name, quantity=it.quantity, unit=it.unit,
            kcal=it.kcal, protein_g=it.protein_g, carbs_g=it.carbs_g, fat_g=it.fat_g,
            cold_warm=it.cold_warm, dry_wet=it.dry_wet,
            source=payload.source,
        ))
    db.commit()
    return day_summary(db, uid, payload.log_date)


@router.get("/meals")
def list_meals(d: date, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_READ)):
    """لیست ردیف‌های غذا یک روز، همراه شناسه برای ویرایش/حذف."""
    uid = _uid(p)
    rows = db.execute(
        select(Meal).where(Meal.user_id == uid, Meal.log_date == d)
        .order_by(Meal.created_at)
    ).scalars().all()
    return {
        "log_date": d,
        "count": len(rows),
        "items": [{
            "id": str(m.id), "slot": m.slot, "item_name": m.item_name,
            "quantity": float(m.quantity), "unit": m.unit,
            "kcal": float(m.kcal), "protein_g": float(m.protein_g),
            "carbs_g": float(m.carbs_g), "fat_g": float(m.fat_g),
            "cold_warm": float(m.cold_warm or 0), "dry_wet": float(m.dry_wet or 0),
        } for m in rows],
    }


@router.patch("/meals/{meal_id}")
def update_meal(meal_id: str, payload: S.MealUpdate, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    """ویرایش یک ردیف غذا. فقط فیلدهای داده‌شده تغییر می‌کنند."""
    uid = _uid(p)
    m = db.get(Meal, meal_id)
    if m is None or str(m.user_id) != str(uid):
        raise HTTPException(404, "meal not found")
    for f in ("slot", "item_name", "quantity", "unit", "kcal", "protein_g",
              "carbs_g", "fat_g", "cold_warm", "dry_wet"):
        v = getattr(payload, f)
        if v is not None:
            setattr(m, f, v)
    db.commit()
    return {"ok": True, "id": str(m.id), "log_date": m.log_date}


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: str, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    """حذف یک ردیف غذا."""
    uid = _uid(p)
    m = db.get(Meal, meal_id)
    if m is None or str(m.user_id) != str(uid):
        raise HTTPException(404, "meal not found")
    d = m.log_date
    db.delete(m)
    db.commit()
    return {"ok": True, "deleted": meal_id, "log_date": d}


@router.post("/log_sleep")
def log_sleep(payload: S.SleepIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(SleepLog).where(
        SleepLog.user_id == uid, SleepLog.log_date == payload.log_date)).scalar_one_or_none()
    if row is None:
        row = SleepLog(user_id=uid, log_date=payload.log_date)
        db.add(row)
    row.bedtime = _parse_dt(payload.bedtime, payload.log_date - timedelta(days=1))
    row.wake_time = _parse_dt(payload.wake_time, payload.log_date)
    for f in ("main_hours", "nap_min", "quality", "wake_count", "note"):
        setattr(row, f, getattr(payload, f))
    db.commit()
    return day_summary(db, uid, payload.log_date)


@router.post("/log_workout")
def log_workout(payload: S.WorkoutIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    w = Workout(
        user_id=uid, log_date=payload.log_date, kind=payload.kind,
        duration_min=payload.duration_min, kcal_burned=payload.kcal_burned,
        muscles=payload.muscles, notes=payload.notes,
    )
    db.add(w)
    db.flush()
    for st in payload.sets:
        db.add(WorkoutSet(workout_id=w.id, exercise=st.exercise, muscle_group=st.muscle_group,
                          sets=st.sets, reps=st.reps, weight_kg=st.weight_kg))
    db.commit()
    return day_summary(db, uid, payload.log_date)


@router.post("/log_body")
def log_body(payload: S.BodyIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(BodyMetric).where(
        BodyMetric.user_id == uid, BodyMetric.measured_at == payload.measured_at)).scalar_one_or_none()
    if row is None:
        row = BodyMetric(user_id=uid, measured_at=payload.measured_at)
        db.add(row)
    for f in ("weight_kg", "body_fat_pct", "visceral_fat", "muscle_kg",
              "muscle_pct", "water_pct", "bmi"):
        setattr(row, f, getattr(payload, f))
    db.commit()
    hist = db.execute(
        select(BodyMetric).where(BodyMetric.user_id == uid)
        .order_by(BodyMetric.measured_at.desc()).limit(30)
    ).scalars().all()
    return {"ok": True, "measured_at": payload.measured_at,
            "weight_kg": payload.weight_kg,
            "history": [{"d": m.measured_at, "w": float(m.weight_kg)} for m in reversed(hist)]}


@router.post("/log_prayer")
def log_prayer(payload: S.PrayerIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(Prayer).where(
        Prayer.user_id == uid, Prayer.log_date == payload.log_date,
        Prayer.prayer == payload.prayer)).scalar_one_or_none()
    if row is None:
        row = Prayer(user_id=uid, log_date=payload.log_date, prayer=payload.prayer,
                     status=payload.status)
        db.add(row)
    else:
        row.status = payload.status
    db.commit()
    return day_summary(db, uid, payload.log_date)


@router.post("/log_mood")
def log_mood(payload: S.MoodIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(MoodLog).where(
        MoodLog.user_id == uid, MoodLog.log_date == payload.log_date)).scalar_one_or_none()
    if row is None:
        row = MoodLog(user_id=uid, log_date=payload.log_date)
        db.add(row)
    row.mood, row.stress, row.energy, row.note = payload.mood, payload.stress, payload.energy, payload.note
    db.commit()
    return day_summary(db, uid, payload.log_date)


@router.post("/log_screen_time")
def log_screen(payload: S.ScreenIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(ScreenTime).where(
        ScreenTime.user_id == uid, ScreenTime.log_date == payload.log_date)).scalar_one_or_none()
    if row is None:
        row = ScreenTime(user_id=uid, log_date=payload.log_date)
        db.add(row)
    for f in ("total_min", "instagram_min", "telegram_min", "other_min",
              "unlocks", "notifications"):
        setattr(row, f, getattr(payload, f))
    db.commit()
    s = get_settings()
    return {
        **day_summary(db, uid, payload.log_date),
        "targets": {"total": s.default_screen_target_min,
                    "instagram": s.default_instagram_target_min},
        "over_target": payload.total_min > s.default_screen_target_min,
    }


@router.post("/log_habit")
def log_habit(payload: S.HabitIn, db: Session = Depends(get_db),
            p: Principal = Depends(HEALTH_WRITE)):
    uid = _uid(p)
    row = db.execute(select(Habit).where(
        Habit.user_id == uid, Habit.log_date == payload.log_date)).scalar_one_or_none()
    if row is None:
        row = Habit(user_id=uid, log_date=payload.log_date)
        db.add(row)
    row.breathing_done = payload.breathing_done
    row.water_liters = payload.water_liters
    row.supplements, row.teas = payload.supplements, payload.teas
    db.commit()
    return day_summary(db, uid, payload.log_date)
