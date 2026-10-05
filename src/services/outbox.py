import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import get_settings
from src.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxRelayService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: Any,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker
        settings = get_settings()
        self._poll_interval = settings.outbox_poll_interval
        self._batch_size = settings.outbox_batch_size
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info(
            "Outbox relay started (interval=%.1fs, batch_limit=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while self._running:
            try:
                await self._poll_and_publish()
            except Exception:
                logger.exception("Outbox relay polling error")
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("Outbox relay stopped")

    async def _poll_and_publish(self) -> None:
        processed_count = 0
        while self._running and processed_count < self._batch_size:
            async with self._session_factory() as session:
                async with session.begin():
                    # SELECT ... FOR UPDATE SKIP LOCKED ensures single worker ownership per record
                    stmt = (
                        select(OutboxEvent)
                        .where(OutboxEvent.status == "pending")
                        .order_by(OutboxEvent.created_at)
                        .limit(1)
                        .with_for_update(skip_locked=True)
                    )
                    event = (await session.execute(stmt)).scalar_one_or_none()
                    if event is None:
                        break

                    try:
                        await self._broker.publish(
                            message=event.payload,
                            exchange="payments.topic",
                            routing_key="payments.new",
                            content_type="application/json",
                        )
                        event.status = "published"
                        event.published_at = datetime.now(timezone.utc)
                        logger.info("Published outbox event %s to payments.new", event.id)
                    except Exception:
                        event.retry_count += 1
                        if event.retry_count >= 5:
                            event.status = "failed"
                        logger.warning(
                            "Failed to publish outbox event %s (attempt %d)",
                            event.id,
                            event.retry_count,
                        )
            processed_count += 1
