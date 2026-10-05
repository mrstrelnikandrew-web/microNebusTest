from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue
from faststream.rabbit.schemas import ExchangeType

from src.config import get_settings

broker = RabbitBroker(url=get_settings().rabbitmq_url)

payments_exchange = RabbitExchange(
    name="payments.topic",
    type=ExchangeType.TOPIC,
    durable=True,
)

dlx_exchange = RabbitExchange(
    name="payments.dlx",
    type=ExchangeType.DIRECT,
    durable=True,
)

payments_queue = RabbitQueue(
    name="payments.new",
    durable=True,
    routing_key="payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.dead",
    },
)

dlq_queue = RabbitQueue(
    name="payments.dlq",
    durable=True,
    routing_key="payments.dead",
)
