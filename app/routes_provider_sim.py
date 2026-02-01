from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from .db import get_db
from .models import User, Transaction
from .schemas import ProviderTopupIn
from .security import require_admin

router = APIRouter(prefix="/provider", tags=["provider"])


@router.post("/topup")
def topup(data: ProviderTopupIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    email = data.user_email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    amt = float(data.amount)
    cur = data.currency

    if cur == "htg":
        user.wallet.htg += amt
    else:
        user.wallet.usd += amt

    # IMPORTANT: direction NOT NULL => on met une valeur
    db.add(Transaction(
        user_id=user.id,
        type="topup",
        currency=cur,
        amount=amt,
        note=data.provider,
        direction="credit",
        rate_used=None,
        created_at=datetime.utcnow(),
    ))

    db.commit()
    return {"ok": True, "credited": {"currency": cur, "amount": amt, "provider": data.provider}}
