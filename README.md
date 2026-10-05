# Payment Processing Service

Асинхронный микросервис процессинга платежей с транзакционным Outbox-паттерном, очередями RabbitMQ, защитой от дублей по Idempotency-Key и доставкой вебхуков с повторными попытками.

## Стек технологий

- Python 3.12, FastAPI, Pydantic v2
- SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16
- RabbitMQ 3.13, FastStream (RabbitBroker)
- HTTPX, Tenacity
- Docker, Docker Compose

## Быстрый старт

1. Скопируйте файл конфигурации:
```bash
cp .env.example .env
```

2. Запустите сервисы:
```bash
docker compose up --build -d
```

После старта доступны:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- RabbitMQ Management: `http://localhost:15672` (логин/пароль: `guest` / `guest`)

## Примеры API запросов

### 1. Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecret-api-key-change-me" \
  -H "Idempotency-Key: pay-test-12345" \
  -d '{
    "amount": 100.50,
    "currency": "RUB",
    "description": "Подписка на сервис",
    "metadata": {"user_id": 42},
    "webhook_url": "https://webhook.site/demo-uuid"
  }'
```

Ответ (`202 Accepted`):
```json
{
  "payment_id": "8b79f826-613d-4c31-9f20-1b77cb2326b4",
  "status": "pending",
  "created_at": "2026-10-05T12:00:00Z"
}
```

### 2. Повторный запрос с тем же Idempotency-Key

Повторный запрос возвращает сохраненную запись без создания дубля:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecret-api-key-change-me" \
  -H "Idempotency-Key: pay-test-12345" \
  -d '{
    "amount": 100.50,
    "currency": "RUB",
    "description": "Подписка на сервис",
    "metadata": {"user_id": 42},
    "webhook_url": "https://webhook.site/demo-uuid"
  }'
```

Ответ (`200 OK`):
```json
{
  "payment_id": "8b79f826-613d-4c31-9f20-1b77cb2326b4",
  "status": "pending",
  "created_at": "2026-10-05T12:00:00Z"
}
```

### 3. Получение информации о платеже

```bash
curl -X GET http://localhost:8000/api/v1/payments/8b79f826-613d-4c31-9f20-1b77cb2326b4 \
  -H "X-API-Key: supersecret-api-key-change-me"
```

Ответ (`200 OK`):
```json
{
  "id": "8b79f826-613d-4c31-9f20-1b77cb2326b4",
  "amount": 100.50,
  "currency": "RUB",
  "description": "Подписка на сервис",
  "metadata": {"user_id": 42},
  "status": "succeeded",
  "webhook_url": "https://webhook.site/demo-uuid",
  "created_at": "2026-10-05T12:00:00Z",
  "updated_at": "2026-10-05T12:00:04Z"
}
```

## Архитектура: Outbox и Dead Letter Queue

1. **Transactional Outbox:**
   - При создании платежа запись в таблицу `payments` и событие в `outbox_events` сохраняются в единой транзакции БД.
   - Фоновый процесс поллера считывает необработанные события запросом `SELECT ... FOR UPDATE SKIP LOCKED` по одной записи, что исключает конфликты и дублирование при горизонтальном масштабировании воркеров.
   - После подтверждения публикации в RabbitMQ (exchange `payments.topic`, routing key `payments.new`) статус события в БД переводится в `published`.

2. **Consumer и Dead Letter Queue (DLQ):**
   - Воркер FastStream слушает очередь `payments.new`, эмулирует ответ провайдера (2–5 сек, 90% успех / 10% отказ) и обновляет статус платежа в БД.
   - Результат отправляется на `webhook_url`. При сетевых сбоях и ошибках `HTTP 5xx` выполняются до 3 повторных попыток с экспоненциальной задержкой (2, 4, 8 сек). Ошибки `4xx` не повторяются.
   - При исчерпании попыток консьюмер отклоняет сообщение вызовом `reject(requeue=False)`. По настроенным аргументам очереди RabbitMQ автоматически перенаправляет сообщение в Dead Letter Exchange `payments.dlx` и сохраняет в очередь `payments.dlq`.

## Запуск тестов

Тесты используют SQLite in-memory и мок брокера сообщений:

```bash
pip install -r requirements.txt -r requirements-dev.txt aiosqlite
pytest -v
```
