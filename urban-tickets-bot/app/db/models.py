# app/db/models.py
from __future__ import annotations

import enum
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, Text,
    DateTime, ForeignKey, func, Enum
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PaymentStatus(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)  # имя из Telegram профиля (не имя билета)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    payments = relationship("Payment", back_populates="user")


class Requisites(Base):
    __tablename__ = "requisites"

    id = Column(Integer, primary_key=True)
    bank = Column(String(255), nullable=False)
    holder = Column(String(255), nullable=False)
    account = Column(String(255), nullable=False)
    comment = Column(String(255), nullable=True)

    active = Column(Boolean, nullable=False, server_default="false")
    usage_count = Column(Integer, nullable=False, server_default="0")
    order_idx = Column(Integer, nullable=False)

    # Новое поле: цена билета для этих реквизитов
    price = Column(Integer, nullable=False, server_default="2500")

    payments = relationship("Payment", back_populates="requisites")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    requisites_id = Column(Integer, ForeignKey("requisites.id"), nullable=False, index=True)

    amount = Column(Integer, nullable=False)
    file_id = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=False)  # "photo" | "document"
    batch_counter = Column(Integer, nullable=False)

    status = Column(
        Enum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        server_default=PaymentStatus.pending.value,
    )

    # Имя на БИЛЕТ (может отличаться от Telegram full_name пользователя)
    ticket_full_name = Column(String(255), nullable=True)

    # Амбассадор/источник (может заполниться опросом/админом)
    ambassador = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="payments")
    requisites = relationship("Requisites", back_populates="payments")
