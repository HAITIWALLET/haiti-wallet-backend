from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from .db import get_db
from .models import Merchant, Subscription, User
from .security import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def compute_next_date(interval: str, count: int):
    now = datetime.utcnow()

    if interval == "day":
        return now + timedelta(days=count)

    if interval == "week":
        return now + timedelta(weeks=count)

    if interval == "month":
        return now + timedelta(days=30 * count)

    if interval == "year":
        return now + timedelta(days=365 * count)

    raise HTTPException(400, "Interval invalide")


@router.post("/create")
def create_subscription(
    api_key: str,
    amount: float,
    currency: str,
    interval: str,
    interval_count: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    merchant = db.query(Merchant).filter(Merchant.api_key == api_key).first()

    if not merchant or not merchant.active:
        raise HTTPException(403, "Merchant invalide")

    next_date = compute_next_date(interval, interval_count)

    sub = Subscription(
        user_id=user.id,
        merchant_id=merchant.id,
        amount=amount,
        currency=currency,
        interval=interval,
        interval_count=interval_count,
        next_billing_date=next_date,
        active=True,
        created_at=datetime.utcnow()
    )

    db.add(sub)
    db.commit()

    return {
        "status": "subscription_created",
        "merchant": merchant.name,
        "next_billing": next_date
    }