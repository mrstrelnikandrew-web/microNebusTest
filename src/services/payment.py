import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.outbox import OutboxEvent
from src.models.payment import Payment
from src.schemas.payment import CreatePaymentRequest, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        result = await self._session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self._session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create_payment(
        self,
        request: CreatePaymentRequest,
        idempotency_key: str,
    ) -> tuple[Payment, bool]:
        existing = await self.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            logger.info("Payment %s found for idempotency key %s", existing.id, idempotency_key)
            return existing, False

        payment = Payment(
            idempotency_key=idempotency_key,
            amount=request.amount,
            currency=request.currency.value,
            description=request.description,
            metadata_info=request.metadata,
            status=PaymentStatus.PENDING.value,
            webhook_url=str(request.webhook_url),
        )
        self._session.add(payment)

        try:
            await self._session.flush()
        except IntegrityError:
            # Handle race condition when another worker committed the same idempotency key
            await self._session.rollback()
            existing = None
            for _ in range(10):
                existing = await self.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    break
                await asyncio.sleep(0.05)

            if existing is None:
                raise

            logger.info("Concurrent insert caught, returning payment %s", existing.id)
            return existing, False

        outbox_event = OutboxEvent(
            event_type="payment.created",
            payload={
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "webhook_url": payment.webhook_url,
                "idempotency_key": payment.idempotency_key,
            },
        )
        self._session.add(outbox_event)

        await self._session.commit()
        await self._session.refresh(payment)

        logger.info("Payment %s created (key=%s)", payment.id, idempotency_key)
        return payment, True

    async def update_status(
        self,
        payment_id: uuid.UUID,
        new_status: str,
    ) -> Payment | None:
        payment = await self.get_by_id(payment_id)
        if payment is None:
            logger.warning("Payment %s not found for status update", payment_id)
            return None

        payment.status = new_status
        payment.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(payment)
        logger.info("Payment %s status updated to %s", payment_id, new_status)
        return payment
