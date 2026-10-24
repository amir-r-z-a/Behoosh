"""مدل‌های SQLAlchemy برای اسکیمای live (دستیار جلسه زنده)."""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class LiveSession(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "live"}

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                       server_default=func.gen_random_uuid())
    user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="recording")
    asr_provider: Mapped[str] = mapped_column(Text, default="sina")
    diarize: Mapped[bool] = mapped_column(Boolean, default=False)
    word_threshold: Mapped[int] = mapped_column(Integer, default=400)
    time_threshold_s: Mapped[int] = mapped_column(Integer, default=90)
    silence_threshold_s: Mapped[int] = mapped_column(Integer, default=6)
    min_words_to_send: Mapped[int] = mapped_column(Integer, default=60)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    # نشانگر آخرین تکه ارسال‌شده. منفی یک یعنی هیچ‌چیز ارسال نشده.
    # صفر نمی‌تواند نشانگر «خالی» باشد چون خودش یک شماره تکه معتبر است.
    last_sent_seq: Mapped[int] = mapped_column(Integer, default=-1)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_token: Mapped[str | None] = mapped_column(Text)
    agent_label: Mapped[str | None] = mapped_column(Text)
    amp_session_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LiveChunk(Base):
    __tablename__ = "chunks"
    __table_args__ = {"schema": "live"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[object] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("live.sessions.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_s: Mapped[float] = mapped_column(Numeric, nullable=False)
    end_s: Mapped[float] = mapped_column(Numeric, nullable=False)
    bytes: Mapped[int | None] = mapped_column(Integer)
    silence: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    asr_job_id: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    words: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LiveSegment(Base):
    __tablename__ = "segments"
    __table_args__ = {"schema": "live"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[object] = mapped_column(UUID(as_uuid=True),
                                               ForeignKey("live.sessions.id", ondelete="CASCADE"))
    from_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    to_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    from_s: Mapped[float] = mapped_column(Numeric, nullable=False)
    to_s: Mapped[float] = mapped_column(Numeric, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    words: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    sent_to_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    send_error: Mapped[str | None] = mapped_column(Text)
    # شناسه پیام ارسالی در کانال AMP. با همین، پاسخ ایجنت به بازه درست وصل می‌شود.
    amp_msg_id: Mapped[str | None] = mapped_column(Text)
    agent_reply: Mapped[str | None] = mapped_column(Text)
    # ایجنت گیرنده این بازه. خالی یعنی نشست قدیمی تک‌ایجنت.
    # نام هم عکس فوری می‌شود تا تاریخچه با پاک شدن ایجنت بی‌نام نماند.
    agent_id: Mapped[object | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live.agents.id", ondelete="SET NULL"))
    agent_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LiveAgent(Base):
    """دفترچه ایجنت‌های کاربر. توکن یک بار ذخیره می‌شود و همیشه می‌ماند.

    توکن هرگز در پاسخ API برنمی‌گردد؛ فقط چهار کاراکتر آخر برای بازشناسی.
    """
    __tablename__ = "agents"
    __table_args__ = {"schema": "live"}

    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                       server_default=func.gen_random_uuid())
    user_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # نتیجه آخرین آزمون توکن. None یعنی هنوز آزموده نشده.
    token_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LiveSessionAgent(Base):
    """پیوند نشست و ایجنت.

    نشست AMP اینجا می‌نشیند نه روی ایجنت. چون توکن AMP به یک نشست قفل است و
    دو جلسه همزمان با یک ایجنت نباید نشست همدیگر را خراب کنند.
    """
    __tablename__ = "session_agents"
    __table_args__ = {"schema": "live"}

    session_id: Mapped[object] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live.sessions.id", ondelete="CASCADE"),
        primary_key=True)
    agent_id: Mapped[object] = mapped_column(
        UUID(as_uuid=True), ForeignKey("live.agents.id", ondelete="CASCADE"),
        primary_key=True)
    amp_session_id: Mapped[str | None] = mapped_column(Text)
    # نشانگر ارسال برای همین ایجنت. اگر یکی خطا بدهد، بقیه متن تکراری نمی‌گیرند.
    last_sent_seq: Mapped[int] = mapped_column(Integer, default=-1)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
