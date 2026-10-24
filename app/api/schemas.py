"""مدل‌های ورودی و خروجی API. اعتبارسنجی در سطح اسکیما، نه رشته."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Slot = Literal["breakfast", "snack", "lunch", "evening", "dinner", "after_dinner"]
Unit = Literal["gram", "spoon", "piece", "glass", "palm", "bowl"]
PrayerName = Literal["fajr", "dhuhr", "asr", "maghrib", "isha"]
PrayerStatus = Literal["done", "late", "qada", "missed"]


def _clamp01(v):
    """بردار مزاج را به بازه -1..1 کلمپ می‌کند. ورودی نامعتبر = 0."""
    if v is None:
        return None
    try:
        return max(-1.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


class MealItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0, default=0)
    unit: Unit = "gram"
    kcal: float = Field(ge=0, default=0)
    protein_g: float = Field(ge=0, default=0)
    carbs_g: float = Field(ge=0, default=0)
    fat_g: float = Field(ge=0, default=0)
    # مزاج دو محوره: منفی=سرد/تر، مثبت=گرم/خشک.
    # مقدار خارج از بازه به -1..1 کلمپ می‌شود (نه رد).
    cold_warm: float = 0
    dry_wet: float = 0

    @field_validator("cold_warm", "dry_wet", mode="before")
    @classmethod
    def _clamp_vec(cls, v):
        return _clamp01(v)


class MealIn(BaseModel):
    log_date: date
    slot: Slot
    items: list[MealItem] = Field(min_length=1)
    source: Literal["user", "db", "agent"] = "agent"


class MealUpdate(BaseModel):
    """ویرایش یک ردیف غذا. فقط فیلدهای داده‌شده تغییر می‌کنند."""
    slot: Slot | None = None
    item_name: str | None = None
    quantity: float | None = Field(ge=0, default=None)
    unit: Unit | None = None
    kcal: float | None = Field(ge=0, default=None)
    protein_g: float | None = Field(ge=0, default=None)
    carbs_g: float | None = Field(ge=0, default=None)
    fat_g: float | None = Field(ge=0, default=None)
    cold_warm: float | None = None
    dry_wet: float | None = None

    @field_validator("cold_warm", "dry_wet", mode="before")
    @classmethod
    def _clamp_vec(cls, v):
        return _clamp01(v)


class SleepIn(BaseModel):
    log_date: date
    # رشته می‌پذیرد: هم "23:30" هم "2026-09-30T23:30:00" (تبدیل در روتر)
    bedtime: str | None = None
    wake_time: str | None = None
    main_hours: float = Field(ge=0, le=24, default=0)
    nap_min: int = Field(ge=0, default=0)
    quality: int = Field(ge=0, le=10, default=0)
    wake_count: int = Field(ge=0, default=0)
    note: str | None = None


class WorkoutSetIn(BaseModel):
    exercise: str
    muscle_group: str | None = None
    sets: int = Field(ge=0, default=0)
    reps: int = Field(ge=0, default=0)
    weight_kg: float = Field(ge=0, default=0)


class WorkoutIn(BaseModel):
    log_date: date
    kind: str
    duration_min: int = Field(ge=0, default=0)
    kcal_burned: float = Field(ge=0, default=0)
    muscles: list[str] = Field(default_factory=list)
    notes: str | None = None
    sets: list[WorkoutSetIn] = Field(default_factory=list)


class BodyIn(BaseModel):
    measured_at: date
    weight_kg: float = Field(ge=0, default=0)
    body_fat_pct: float = Field(ge=0, default=0)
    visceral_fat: float = Field(ge=0, default=0)
    muscle_kg: float = Field(ge=0, default=0)
    muscle_pct: float = Field(ge=0, default=0)
    water_pct: float = Field(ge=0, default=0)
    bmi: float = Field(ge=0, default=0)


class PrayerIn(BaseModel):
    log_date: date
    prayer: PrayerName
    status: PrayerStatus


class MoodIn(BaseModel):
    log_date: date
    mood: int = Field(ge=0, le=10, default=0)
    stress: int = Field(ge=0, le=10, default=0)
    energy: int = Field(ge=0, le=10, default=0)
    note: str | None = None


class ScreenIn(BaseModel):
    log_date: date
    total_min: int = Field(ge=0, default=0)
    instagram_min: int = Field(ge=0, default=0)
    telegram_min: int = Field(ge=0, default=0)
    other_min: int = Field(ge=0, default=0)
    unlocks: int = Field(ge=0, default=0)
    notifications: int = Field(ge=0, default=0)


class HabitIn(BaseModel):
    log_date: date
    breathing_done: bool = False
    water_liters: float = Field(ge=0, default=0)
    supplements: list[str] = Field(default_factory=list)
    teas: list[str] = Field(default_factory=list)


class TemperamentProfileIn(BaseModel):
    base_cold_warm: float = 0
    base_dry_wet: float = 0

    @field_validator("base_cold_warm", "base_dry_wet", mode="before")
    @classmethod
    def _clamp(cls, v):
        return _clamp01(v)
    constitution: str | None = None
    method: Literal["modern", "traditional", "hybrid"] = "hybrid"
    note: str | None = None


class TemperamentExamIn(BaseModel):
    organ: str = Field(min_length=1)
    cold_warm: float = 0
    dry_wet: float = 0

    @field_validator("cold_warm", "dry_wet", mode="before")
    @classmethod
    def _clamp(cls, v):
        return _clamp01(v)
    severity: int = Field(ge=0, le=3, default=0)
    finding: str | None = None
    source: Literal["user", "db", "agent"] = "agent"
    measured_at: date


class TemperamentVectorIn(BaseModel):
    item_name: str = Field(min_length=1)
    item_type: Literal["food", "behavior", "intervention"] = "food"
    cold_warm: float = 0
    dry_wet: float = 0

    @field_validator("cold_warm", "dry_wet", mode="before")
    @classmethod
    def _clamp(cls, v):
        return _clamp01(v)
    source_ref: str | None = None
