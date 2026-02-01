from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, Transaction, Partner
from .security import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.post("/spend")
def spend_wallet(
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    partner_id = data.get("partner_id")
    currency = (data.get("currency") or "").lower()
    amount = float(data.get("amount") or 0)
    note = (data.get("note") or "").strip()

    if currency not in ("htg", "usd"):
        raise HTTPException(status_code=400, detail="Devise invalide")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Montant invalide")
    if not partner_id:
        raise HTTPException(status_code=400, detail="Partenaire requis")

    p = db.query(Partner).filter(Partner.id == int(partner_id)).first()
    if not p or (hasattr(p, "active") and not p.active):
        raise HTTPException(status_code=404, detail="Partenaire introuvable ou inactif")

    # solde
    if currency == "htg":
        if user.wallet.htg < amount:
            raise HTTPException(status_code=400, detail="Solde HTG insuffisant")
        user.wallet.htg -= amount
    else:
        if user.wallet.usd < amount:
            raise HTTPException(status_code=400, detail="Solde USD insuffisant")
        user.wallet.usd -= amount

    tx = Transaction(
        user_id=user.id,
        type="spend",
        currency=currency,
        amount=amount,
        note=f"Paiement partenaire: {p.name}" + (f" | {note}" if note else ""),
        direction="spend",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)
    db.commit()

    return {"ok": True}
