"""روترهای ثبت و خواندن داده."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import schemas as S
from app.api.auth_deps import Principal
from app.api.deps import require_token
from app.api.summary import day_summary
from app.db.models import (
    BodyMetric, Habit, Meal, MoodLog, Prayer, ScreenTime, SleepLog, Workout, WorkoutSet,
    TemperamentExam, TemperamentProfile, TemperamentState, TemperamentVector,
)
from app.db.session import get_db
from app.core.config import get_settings

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


def _uid(p) -> str:
    """user_id از توکن می‌آید، نه از دیتابیس. مرز امنیتی."""
    return p.user_id


def _parse_dt(value: str | None, base: date) -> datetime | None:
    """رشته ساعت را به datetime تبدیل می‌کند. هم '23:30' هم ISO کامل."""
    if not value:
        return None
    v = value.strip()
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    try:
        t = time.fromisoformat(v)
        return datetime.combine(base, t)
    except ValueError:
        raise HTTPException(422, f"bad time format: {value!r} (use HH:MM or ISO)")


@router.post("/log_meal")
def log_meal(payload: S.MealIn, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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
            p: Principal = Depends(require_token)):
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


@router.get("/day_summary")
def get_day_summary(d: date | None = None,
                    date_q: date | None = Query(None, alias="date"),
                    db: Session = Depends(get_db),
                    p: Principal = Depends(require_token)):
    """جمع روز. هم پارامتر d و هم date پذیرفته می‌شود. احراز هویت توکنی."""
    return day_summary(db, _uid(p), d or date_q or date.today())


@router.get("/trends")
def get_trends(metric: str, days: int = 14, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    uid = _uid(p)
    start = date.today() - timedelta(days=days - 1)
    if metric in ("kcal", "meals"):
        rows = db.execute(
            select(Meal.log_date, Meal.kcal).where(
                Meal.user_id == uid, Meal.log_date >= start)).all()
        agg: dict = {}
        for d_, k in rows:
            agg[d_] = agg.get(d_, 0) + float(k)
        return {"metric": metric, "points": [{"d": k, "v": v} for k, v in sorted(agg.items())]}
    if metric == "weight":
        rows = db.execute(
            select(BodyMetric.measured_at, BodyMetric.weight_kg).where(
                BodyMetric.user_id == uid, BodyMetric.measured_at >= start)
            .order_by(BodyMetric.measured_at)).all()
        return {"metric": metric, "points": [{"d": d_, "v": float(w)} for d_, w in rows]}
    if metric == "sleep":
        rows = db.execute(
            select(SleepLog.log_date, SleepLog.main_hours).where(
                SleepLog.user_id == uid, SleepLog.log_date >= start)
            .order_by(SleepLog.log_date)).all()
        return {"metric": metric, "points": [{"d": d_, "v": float(h)} for d_, h in rows]}
    if metric == "protein":
        rows = db.execute(
            select(Meal.log_date, Meal.protein_g).where(
                Meal.user_id == uid, Meal.log_date >= start)).all()
        agg = {}
        for d_, p in rows:
            agg[d_] = agg.get(d_, 0) + float(p)
        return {"metric": metric, "points": [{"d": k, "v": v} for k, v in sorted(agg.items())]}
    if metric == "temperament":
        from app.db.models import TemperamentState
        rows = db.execute(
            select(TemperamentState.log_date, TemperamentState.cold_warm,
                   TemperamentState.dry_wet).where(
                TemperamentState.user_id == uid, TemperamentState.log_date >= start)
            .order_by(TemperamentState.log_date)).all()
        return {"metric": metric, "points": [
            {"d": d_, "cw": float(cw), "dw": float(dw)} for d_, cw, dw in rows]}
    raise HTTPException(400, f"unknown metric: {metric}")


@router.post("/temperament_profile")
def set_temperament_profile(payload: S.TemperamentProfileIn, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """ثبت/به‌روزرسانی مزاج پایه کاربر (نقطه لنگر صفحه دو محوره)."""
    uid = _uid(p)
    row = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    if row is None:
        row = TemperamentProfile(user_id=uid)
        db.add(row)
    row.base_cold_warm = payload.base_cold_warm
    row.base_dry_wet = payload.base_dry_wet
    row.constitution = payload.constitution
    row.method = payload.method
    row.note = payload.note
    db.commit()
    return {"ok": True, "base_cold_warm": float(row.base_cold_warm),
            "base_dry_wet": float(row.base_dry_wet),
            "constitution": row.constitution, "method": row.method}


@router.get("/temperament_profile")
def get_temperament_profile(db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """مزاج پایه کاربر. اگر ثبت نشده، پیش‌فرض صفر."""
    uid = _uid(p)
    row = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    if row is None:
        return {"base_cold_warm": 0, "base_dry_wet": 0,
                "constitution": None, "method": "hybrid", "set": False}
    return {"base_cold_warm": float(row.base_cold_warm),
            "base_dry_wet": float(row.base_dry_wet),
            "constitution": row.constitution, "method": row.method, "set": True}


@router.post("/log_temperament_exam")
def log_temperament_exam(payload: S.TemperamentExamIn, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """ثبت بردار مزاج یک عضو از معاینه. کلید یکتا: (user_id, organ)."""
    uid = _uid(p)
    row = db.execute(select(TemperamentExam).where(
        TemperamentExam.user_id == uid,
        TemperamentExam.organ == payload.organ)).scalar_one_or_none()
    if row is None:
        row = TemperamentExam(user_id=uid, organ=payload.organ)
        db.add(row)
    row.cold_warm = payload.cold_warm
    row.dry_wet = payload.dry_wet
    row.severity = payload.severity
    row.finding = payload.finding
    row.source = payload.source
    row.measured_at = payload.measured_at
    db.commit()
    return {"ok": True, "organ": payload.organ,
            "cold_warm": payload.cold_warm, "dry_wet": payload.dry_wet,
            "severity": payload.severity}


@router.get("/temperament_exam")
def get_temperament_exam(db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """لیست معاینه ارگان‌ها + میانگین بردار (مبنای مزاج پایه)."""
    uid = _uid(p)
    rows = db.execute(select(TemperamentExam).where(
        TemperamentExam.user_id == uid).order_by(TemperamentExam.organ)).scalars().all()
    if not rows:
        return {"count": 0, "organs": [], "avg_cold_warm": 0, "avg_dry_wet": 0}
    cw = sum(float(r.cold_warm) for r in rows) / len(rows)
    dw = sum(float(r.dry_wet) for r in rows) / len(rows)
    return {
        "count": len(rows),
        "organs": [{"organ": r.organ, "cold_warm": float(r.cold_warm),
                     "dry_wet": float(r.dry_wet), "severity": r.severity,
                     "finding": r.finding, "measured_at": r.measured_at}
                    for r in rows],
        "avg_cold_warm": round(cw, 3), "avg_dry_wet": round(dw, 3),
    }


@router.post("/log_temperament_vector")
def log_temperament_vector(payload: S.TemperamentVectorIn, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """ثبت/ویرایش بردار پایه یک قلم (غذا/رفتار/مداخله)."""
    uid = _uid(p)
    row = db.execute(select(TemperamentVector).where(
        TemperamentVector.item_name == payload.item_name,
        TemperamentVector.item_type == payload.item_type)).scalar_one_or_none()
    if row is None:
        row = TemperamentVector(item_name=payload.item_name, item_type=payload.item_type)
        db.add(row)
    row.cold_warm = payload.cold_warm
    row.dry_wet = payload.dry_wet
    row.source_ref = payload.source_ref
    row.verified = bool(payload.source_ref)
    db.commit()
    return {"ok": True, "item_name": payload.item_name,
            "cold_warm": payload.cold_warm, "dry_wet": payload.dry_wet,
            "verified": row.verified}


@router.get("/temperament_vectors")
def list_temperament_vectors(item_type: str | None = None, q: str | None = None,
                             db: Session = Depends(get_db)):
    """لیست بردارهای پایه، با فیلتر نوع و جستجوی نام."""
    stmt = select(TemperamentVector)
    if item_type:
        stmt = stmt.where(TemperamentVector.item_type == item_type)
    if q:
        stmt = stmt.where(TemperamentVector.item_name.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(TemperamentVector.item_name)).scalars().all()
    return {"count": len(rows), "items": [
        {"item_name": r.item_name, "item_type": r.item_type,
         "cold_warm": float(r.cold_warm), "dry_wet": float(r.dry_wet),
         "verified": r.verified, "source_ref": r.source_ref} for r in rows]}


@router.get("/temperament_state")
def get_temperament_state(d: date | None = None, db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    """نقطه مزاج کنونی: بردار پایه + بردار امروز."""
    from app.temperament import day_vector, label, state_vector
    uid = _uid(p)
    target = d or date.today()
    prof = db.execute(select(TemperamentProfile).where(
        TemperamentProfile.user_id == uid)).scalar_one_or_none()
    base = {"cold_warm": float(prof.base_cold_warm) if prof else 0,
            "dry_wet": float(prof.base_dry_wet) if prof else 0}
    dcw, ddw, n = day_vector(db, uid, target)
    scw, sdw = state_vector(db, uid, target)
    return {"log_date": target, "base": base,
            "today": {"cold_warm": round(dcw, 3), "dry_wet": round(ddw, 3),
                       "label": label(dcw, ddw) if n else "بدون داده", "items": n},
            "state": {"cold_warm": round(scw, 3), "dry_wet": round(sdw, 3),
                       "label": label(scw, sdw)}}


@router.get("/targets")
def get_targets(db: Session = Depends(get_db),
            p: Principal = Depends(require_token)):
    s = get_settings()
    return {
        "kcal": s.default_kcal_target,
        "protein_g": s.default_protein_target,
        "sleep_hours": s.default_sleep_target,
        "screen_total_min": s.default_screen_target_min,
        "screen_instagram_min": s.default_instagram_target_min,
    }
