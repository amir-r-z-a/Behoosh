"""مدل‌های مالی. اسکیمای جدا: finance. مدل دوبل‌انتری سبک."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class FinAccount(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "name"), {"schema": "finance"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="IRT")
    card_last4: Mapped[str | None] = mapped_column(Text)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinCategory(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", "kind"), {"schema": "finance"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.categories.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinTransaction(Base):
    __tablename__ = "transactions"
    __table_args__ = ({"schema": "finance"},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.categories.id", ondelete="SET NULL"))
    counterparty: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="manual")
    external_ref: Mapped[str | None] = mapped_column(Text)
    raw_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # انتقال بین حساب‌های خود کاربر هزینه نیست؛ با این پرچم از جمع هزینه بیرون می‌رود.
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # اگر این تراکنش قسط یک وام است، به همان وام وصل می‌شود.
    liability_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.liabilities.id", ondelete="SET NULL"))
    # دریافت اصل وام درآمد نیست. این پرچم تراکنش را از خلاصه درآمد/هزینه
    # بیرون می‌برد تا گزارش درآمد کاربر چند صد میلیون بیشتر از واقعیت نشود.
    exclude_from_summary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    entries: Mapped[list["FinEntry"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan")


class FinEntry(Base):
    __tablename__ = "entries"
    __table_args__ = ({"schema": "finance"},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance.transactions.id", ondelete="CASCADE"))
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance.accounts.id", ondelete="RESTRICT"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    transaction: Mapped[FinTransaction] = relationship(back_populates="entries")


class FinBudget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category_id", "period"), {"schema": "finance"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("finance.categories.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(Text, default="monthly")
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinRawMessage(Base):
    __tablename__ = "raw_messages"
    __table_args__ = ({"schema": "finance"},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text, default="sms")
    bank: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    parsed: Mapped[bool] = mapped_column(Boolean, default=False)
    parse_error: Mapped[str | None] = mapped_column(Text)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.transactions.id", ondelete="SET NULL"))


class FinAudit(Base):
    __tablename__ = "audit_log"
    __table_args__ = ({"schema": "finance"},)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(Text, default="agent")
    token_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinLiability(Base):
    """بدهی و تعهد: وام، قسط، قرض.

    چرا جدا از تراکنش: اصل وام پول تازه است نه درآمد. اگر به‌عنوان درآمد
    ثبت شود گزارش ماه بهتر از واقعیت می‌شود. اینجا اصل، مانده و سررسید
    نگه داشته می‌شود و هر قسط به وامش وصل می‌شود.
    """
    __tablename__ = "liabilities"
    __table_args__ = (UniqueConstraint("user_id", "name"), {"schema": "finance"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, default="loan")
    principal: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    interest_rate: Mapped[float] = mapped_column(Numeric(6, 3), default=0)
    installments_total: Mapped[int] = mapped_column(Integer, default=0)
    installment_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_day: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("finance.accounts.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, default="active")
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
