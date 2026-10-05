import uuid

import pytest

PAYMENT_PAYLOAD = {
    "amount": 100.50,
    "currency": "RUB",
    "description": "Test subscription",
    "metadata": {"user_id": 42},
    "webhook_url": "https://webhook.site/test-uuid",
}


@pytest.mark.asyncio
async def test_create_payment_missing_api_key(client):
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_PAYLOAD,
        headers={
            "X-API-Key": "",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key"


@pytest.mark.asyncio
async def test_create_payment_wrong_api_key(client):
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_PAYLOAD,
        headers={
            "X-API-Key": "wrong-key",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_payment_success(client):
    idempotency_key = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_PAYLOAD,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert response.status_code == 202
    body = response.json()
    assert "payment_id" in body
    assert body["status"] == "pending"
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_payment_missing_idempotency_key(client):
    response = await client.post("/api/v1/payments", json=PAYMENT_PAYLOAD)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_invalid_currency(client):
    response = await client.post(
        "/api/v1/payments",
        json={**PAYMENT_PAYLOAD, "currency": "GBP"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_negative_amount(client):
    response = await client.post(
        "/api/v1/payments",
        json={**PAYMENT_PAYLOAD, "amount": -10},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_idempotent_create_payment(client):
    idempotency_key = str(uuid.uuid4())
    headers = {"Idempotency-Key": idempotency_key}

    resp1 = await client.post("/api/v1/payments", json=PAYMENT_PAYLOAD, headers=headers)
    resp2 = await client.post("/api/v1/payments", json=PAYMENT_PAYLOAD, headers=headers)

    assert resp1.status_code == 202
    assert resp2.status_code == 200
    assert resp1.json()["payment_id"] == resp2.json()["payment_id"]


@pytest.mark.asyncio
async def test_create_payment_idempotency_key_too_long(client):
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_PAYLOAD,
        headers={"Idempotency-Key": "x" * 256},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_payment_success(client):
    idempotency_key = str(uuid.uuid4())
    create_resp = await client.post(
        "/api/v1/payments",
        json=PAYMENT_PAYLOAD,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert create_resp.status_code == 202
    payment_id = create_resp.json()["payment_id"]

    get_resp = await client.get(f"/api/v1/payments/{payment_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["id"] == payment_id
    assert body["status"] == "pending"
    assert body["currency"] == "RUB"
    assert float(body["amount"]) == pytest.approx(100.50)
    assert body["metadata"]["user_id"] == 42


@pytest.mark.asyncio
async def test_get_payment_not_found(client):
    response = await client.get(f"/api/v1/payments/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
