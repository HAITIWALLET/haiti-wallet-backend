from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Subscription, Wallet, Transaction


def compute_next_date(interval, count):
    if interval == "day":
        return datetime.utcnow() + timedelta(days=count)

    if interval == "week":
        return datetime.utcnow() + timedelta(weeks=count)

    if interval == "month":
        return datetime.utcnow() + timedelta(days=30 * count)

    if interval == "year":
        return datetime.utcnow() + timedelta(days=365 * count)


def run_subscription_billing():

    db: Session = SessionLocal()

    subs = db.query(Subscription).filter(
        Subscription.active == True,
        Subscription.next_billing_date <= datetime.utcnow()
    ).all()

    for sub in subs:

        wallet = db.query(Wallet).filter(
            Wallet.user_id == sub.user_id
        ).first()

        if not wallet:
            continue

        if sub.currency.lower() == "htg":

            if wallet.htg < sub.amount:
                continue

            wallet.htg -= sub.amount

        elif sub.currency.lower() == "usd":

            if wallet.usd < sub.amount:
                continue

            wallet.usd -= sub.amount

        tx = Transaction(
            user_id=sub.user_id,
            type="subscription_payment",
            currency=sub.currency,
            amount=sub.amount,
            note="Subscription payment",
            direction="debit",
            created_at=datetime.utcnow(),
        )

        db.add(tx)

        sub.next_billing_date = compute_next_date(
            sub.interval,
            sub.interval_count
        )

    db.commit()
    db.close()