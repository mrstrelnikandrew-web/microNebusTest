import uuid

from fastapi import APIRouter, HTTPException, Response, status

from src.api.deps import ApiKeyDep, DbSession, IdempotencyKeyDep
from src.schemas.payment import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentDetailResponse,
)
from src.services.payment import PaymentService

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreatePaymentResponse,
    responses={
        200: {"description": "Existing payment returned (idempotency key matched)"},
        202: {"description": "New payment accepted for processing"},
    },
)
async def create_payment(
    body: CreatePaymentRequest,
    _auth: ApiKeyDep,
    session: DbSession,
    idempotency_key: IdempotencyKeyDep,
    response: Response,
) -> CreatePaymentResponse:
    service = PaymentService(session)
    payment, created = await service.create_payment(body, idempotency_key)

    if not created:
        response.status_code = status.HTTP_200_OK

    return CreatePaymentResponse(
        payment_id=payment.id,
        status=payment.status,  # type: ignore[arg-type]
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailResponse,
    responses={
        404: {"description": "Payment not found"},
    },
)
async def get_payment(
    payment_id: uuid.UUID,
    _auth: ApiKeyDep,
    session: DbSession,
) -> PaymentDetailResponse:
    payment = await PaymentService(session).get_by_id(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found",
        )
    return PaymentDetailResponse.model_validate(payment)
