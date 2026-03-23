from sqlalchemy.ext.asyncio import AsyncSession
from ..db.crud import increment_usage_and_rotate_if_needed

async def handle_rotation_after_payment(session: AsyncSession, requisites_id: int) -> int:
    """Инкремент usage_count и ротация при достижении 20. Возвращает batch_counter (1..20)."""
    return await increment_usage_and_rotate_if_needed(session, requisites_id)
