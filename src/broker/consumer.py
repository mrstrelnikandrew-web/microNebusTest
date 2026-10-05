import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from faststream.rabbit import RabbitMessage

from src.broker.setup import broker, dlq_queue, dlx_exchange, payments_exchange, payments_queue
from src.database import async_session_factory
from src.schemas.payment import PaymentMessage
from src.services.payment import PaymentService
from src.services.webhook import WebhookService

logger = logging.getLogger(__name__)

_webhook_service = WebhookService()


@broker.subscriber(dlq_queue, dlx_exchange)
async def handle_dlq(message: dict) -> None:
    logger.warning("Message routed to DLQ: %s", message)


@broker.subscriber(payments_queue, payments_exchange)
async def process_payment(
    message: PaymentMessage,
    raw_message: RabbitMessage,
) -> None:
    payment_id_str = message.payment_id
    logger.info("Processing payment %s", payment_id_str)

    # Simulate payment provider processing delay (2-5s)
    await asyncio.sleep(random.uniform(2, 5))

    outcome = "succeeded" if random.random() < 0.9 else "failed"
    logger.info("Gateway result for %s: %s", payment_id_str, outcome)

    payment_id = uuid.UUID(payment_id_str)
    async with async_session_factory() as session:
        service = PaymentService(session)
        payment = await service.update_status(payment_id, outcome)

    if payment is None:
        logger.error("Payment %s not found in database, acknowledging to drop", payment_id_str)
        await raw_message.ack()
        return

    webhook_payload = {
        "payment_id": payment_id_str,
        "status": outcome,
        "amount": message.amount,
        "currency": message.currency,
        "idempotency_key": message.idempotency_key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await _webhook_service.deliver(message.webhook_url, webhook_payload)
        logger.info("Webhook sent successfully for payment %s", payment_id_str)
    except Exception as exc:
        logger.error(
            "Webhook failed for payment %s after retries (%s), rejecting to DLQ",
            payment_id_str,
            exc,
        )
        await raw_message.reject(requeue=False)
        raise
