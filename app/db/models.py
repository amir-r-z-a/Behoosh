"""مدل‌های SQLAlchemy — آینه اسکیمای migrations/."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(Text)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Tehran")
    language: Mapped[str] = mapped_column(Text, default="fa")
    method: Mapped[str] = mapped_column(Text, default="hybrid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (UniqueConstraint("user_id", "goal_type"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    goal_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric, default=0)
    target_unit: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, default=0)
    unit: Mapped[str] = mapped_column(Text, default="gram")
    kcal: Mapped[float] = mapped_column(Numeric, default=0)
    protein_g: Mapped[float] = mapped_column(Numeric, default=0)
    carbs_g: Mapped[float] = mapped_column(Numeric, default=0)
    fat_g: Mapped[float] = mapped_column(Numeric, default=0)
    cold_warm: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    dry_wet: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    source: Mapped[str] = mapped_column(Text, default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_min: Mapped[int] = mapped_column(Integer, default=0)
    kcal_burned: Mapped[float] = mapped_column(Numeric, default=0)
    muscles: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sets: Mapped[list["WorkoutSet"]] = relationship(back_populates="workout", cascade="all, delete-orphan")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"))
    exercise: Mapped[str] = mapped_column(Text, nullable=False)
    muscle_group: Mapped[str | None] = mapped_column(Text)
    sets: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[float] = mapped_column(Numeric, default=0)
    workout: Mapped[Workout] = relationship(back_populates="sets")


class SleepLog(Base):
    __tablename__ = "sleep_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    bedtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wake_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    main_hours: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    nap_min: Mapped[int] = mapped_column(Integer, default=0)
    quality: Mapped[int] = mapped_column(SmallInteger, default=0)
    wake_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)


class BodyMetric(Base):
    __tablename__ = "body_metrics"
    __table_args__ = (UniqueConstraint("user_id", "measured_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    body_fat_pct: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    visceral_fat: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    muscle_kg: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    muscle_pct: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    water_pct: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    bmi: Mapped[float] = mapped_column(Numeric(4, 1), default=0)
    labs: Mapped[dict] = mapped_column(JSONB, default=dict)


class Prayer(Base):
    __tablename__ = "prayers"
    __table_args__ = (UniqueConstraint("user_id", "log_date", "prayer"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    prayer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)


class MoodLog(Base):
    __tablename__ = "mood_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[int] = mapped_column(SmallInteger, default=0)
    stress: Mapped[int] = mapped_column(SmallInteger, default=0)
    energy: Mapped[int] = mapped_column(SmallInteger, default=0)
    symptoms: Mapped[dict] = mapped_column(JSONB, default=dict)
    note: Mapped[str | None] = mapped_column(Text)


class ScreenTime(Base):
    __tablename__ = "screen_time"
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_min: Mapped[int] = mapped_column(Integer, default=0)
    instagram_min: Mapped[int] = mapped_column(Integer, default=0)
    telegram_min: Mapped[int] = mapped_column(Integer, default=0)
    other_min: Mapped[int] = mapped_column(Integer, default=0)
    unlocks: Mapped[int] = mapped_column(Integer, default=0)
    notifications: Mapped[int] = mapped_column(Integer, default=0)


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    breathing_done: Mapped[bool] = mapped_column(Boolean, default=False)
    water_liters: Mapped[float] = mapped_column(Numeric(3, 1), default=0)
    supplements: Mapped[list] = mapped_column(JSONB, default=list)
    teas: Mapped[list] = mapped_column(JSONB, default=list)
    interventions: Mapped[list] = mapped_column(JSONB, default=list)



class TemperamentVector(Base):
    __tablename__ = "temperament_vectors"
    __table_args__ = (UniqueConstraint("item_name", "item_type"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_name: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    cold_warm: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    dry_wet: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    max_weight: Mapped[float] = mapped_column(Numeric, default=1)
    decay_lambda: Mapped[float] = mapped_column(Numeric, default=0.1)
    source_ref: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class TemperamentState(Base):
    __tablename__ = "temperament_state"
    __table_args__ = (UniqueConstraint("user_id", "log_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    cold_warm: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    dry_wet: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



class TemperamentProfile(Base):
    __tablename__ = "temperament_profile"
    __table_args__ = (UniqueConstraint("user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    base_cold_warm: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    base_dry_wet: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    constitution: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text, default="hybrid")
    note: Mapped[str | None] = mapped_column(Text)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemperamentExam(Base):
    __tablename__ = "temperament_exam"
    __table_args__ = (UniqueConstraint("user_id", "organ"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organ: Mapped[str] = mapped_column(Text, nullable=False)
    cold_warm: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    dry_wet: Mapped[float] = mapped_column(Numeric(4, 3), default=0)
    severity: Mapped[int] = mapped_column(SmallInteger, default=0)
    finding: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="agent")
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
