from __future__ import annotations

import os
from typing import Optional, Sequence

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Requisites, Payment, PaymentStatus

PRICE = int((os.getenv("PRICE_RUB") or 2500))


# ---------- USERS ----------

async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: Optional[str],
    full_name: Optional[str],
) -> User:
    q = await session.execute(select(User).where(User.tg_id == tg_id))
    user = q.scalar_one_or_none()
    if user:
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if changed:
            await session.flush()
        return user
    user = User(tg_id=tg_id, username=username, full_name=full_name)
    session.add(user)
    await session.flush()
    return user


# ---------- REQUISITES ----------

async def get_active_requisites(session: AsyncSession) -> Optional[Requisites]:
    q = await session.execute(select(Requisites).where(Requisites.active == True))
    return q.scalar_one_or_none()

async def list_requisites(session: AsyncSession) -> Sequence[Requisites]:
    q = await session.execute(select(Requisites).order_by(Requisites.order_idx))
    return q.scalars().all()

async def add_requisites(
    session: AsyncSession,
    bank: str,
    holder: str,
    account: str,
    comment: str,
    order_idx: int,
    price: int,                      # <--- НОВЫЙ аргумент
    active: bool = False
) -> Requisites:
    req = Requisites(
        bank=bank,
        holder=holder,
        account=account,
        comment=comment,
        order_idx=order_idx,
        price=price,                # <--- сохраняем цену
        active=active,
        usage_count=0
    )
    session.add(req)
    await session.flush()
    return req


async def set_active_requisites(session: AsyncSession, requisites_id: int):
    await session.execute(update(Requisites).values(active=False))
    await session.execute(
        update(Requisites)
        .where(Requisites.id == requisites_id)
        .values(active=True, usage_count=0)
    )

async def rotate_to_next(session: AsyncSession):
    current = await get_active_requisites(session)
    if not current:
        return None
    q = await session.execute(
        select(Requisites)
        .where(Requisites.order_idx > current.order_idx)
        .order_by(Requisites.order_idx.asc())
        .limit(1)
    )
    next_req = q.scalar_one_or_none()
    if not next_req:
        q2 = await session.execute(
            select(Requisites).order_by(Requisites.order_idx.asc()).limit(1)
        )
        next_req = q2.scalar_one_or_none()
    if not next_req or next_req.id == current.id:
        return current
    await session.execute(
        update(Requisites).where(Requisites.id == current.id).values(active=False)
    )
    await session.execute(
        update(Requisites)
        .where(Requisites.id == next_req.id)
        .values(active=True, usage_count=0)
    )
    return next_req

async def increment_usage_and_rotate_if_needed(session: AsyncSession, requisites_id: int) -> int:
    row = await session.execute(
        select(Requisites).where(Requisites.id == requisites_id).with_for_update()
    )
    req = row.scalar_one_or_none()
    if not req:
        raise RuntimeError("Requisites not found for increment")

    new_count = (req.usage_count or 0) + 1
    await session.execute(
        update(Requisites).where(Requisites.id == requisites_id).values(usage_count=new_count)
    )

    if new_count >= 20 and req.active:
        await rotate_to_next(session)

    return new_count


# ---------- PAYMENTS ----------

async def create_payment(
    session: AsyncSession,
    user_id: int,
    requisites_id: int,
    amount: int,
    file_id: str,
    file_type: str,
    batch_counter: int,
    ticket_full_name: Optional[str] = None,
    ambassador: Optional[str] = None,
) -> Payment:
    p = Payment(
        user_id=user_id,
        requisites_id=requisites_id,
        amount=amount,
        file_id=file_id,
        file_type=file_type,
        batch_counter=batch_counter,
        status=PaymentStatus.pending,
        ticket_full_name=ticket_full_name,
        ambassador=ambassador,
    )
    session.add(p)
    await session.flush()
    return p

async def set_payment_status(session: AsyncSession, payment_id: int, new_status: PaymentStatus):
    await session.execute(
        update(Payment).where(Payment.id == payment_id).values(status=new_status)
    )

async def set_payment_ambassador(session: AsyncSession, payment_id: int, amb: str):
    await session.execute(
        update(Payment).where(Payment.id == payment_id).values(ambassador=amb)
    )


# ---------- STATS ----------

async def stats(session: AsyncSession):
    q_total = await session.execute(select(func.count(Payment.id)))
    total = q_total.scalar() or 0

    active = await get_active_requisites(session)
    remain = 20 - (active.usage_count or 0) if active else None

    q_group = await session.execute(
        select(Payment.requisites_id, func.count(Payment.id)).group_by(Payment.requisites_id)
    )
    per_req = {rid: cnt for rid, cnt in q_group.all()}

    return {
        "total": total,
        "active_id": active.id if active else None,
        "active_usage": active.usage_count if active else None,
        "remain_to_rotate": remain,
        "per_requisites": per_req,
    }
