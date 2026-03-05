from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from .db import get_db
from .models import Merchant, User, Wallet, Transaction
from .security import get_current_user

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.post("/pay")
def merchant_pay(
    api_key: str,
    amount: float,
    currency: str,
    description: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):

    merchant = db.query(Merchant).filter(Merchant.api_key == api_key).first()

    if not merchant or not merchant.active:
        raise HTTPException(403, "Merchant invalide")

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()

    if not wallet:
        raise HTTPException(400, "Wallet introuvable")

    if currency.lower() == "htg":
        if wallet.htg < amount:
            raise HTTPException(400, "Solde insuffisant")
        wallet.htg -= amount

    elif currency.lower() == "usd":
        if wallet.usd < amount:
            raise HTTPException(400, "Solde insuffisant")
        wallet.usd -= amount

    else:
        raise HTTPException(400, "Devise invalide")

    tx = Transaction(
        user_id=user.id,
        type="merchant_payment",
        currency=currency,
        amount=amount,
        note=description or f"Paiement {merchant.name}",
        direction="debit",
        created_at=datetime.utcnow(),
    )

    db.add(tx)

    db.commit()

    return {
        "status": "success",
        "merchant": merchant.name,
        "amount": amount,
        "currency": currency
    }