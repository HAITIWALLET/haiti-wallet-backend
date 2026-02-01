from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, Transaction, Partner
from .schemas import PartnerSpendIn, PartnerSpendOut
from .security import get_current_user

router = APIRouter(prefix="/partners", tags=["partners"])

@router.post("/spend", response_model=PartnerSpendOut)
def spend_at_partner(
    data: PartnerSpendIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # validate
    if data.currency not in ("htg", "usd"):
        raise HTTPException(status_code=400, detail="Devise invalide")
    amt = float(data.amount or 0)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Montant invalide")

    # partner
    p = db.query(Partner).filter(Partner.id == data.partner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Partenaire introuvable")
    if hasattr(p, "active") and (p.active is False):
        raise HTTPException(status_code=400, detail="Partenaire inactif")

    # check & debit
    if not user.wallet:
        raise HTTPException(status_code=400, detail="Wallet introuvable")

    if data.currency == "htg":
        if float(user.wallet.htg) < amt:
            raise HTTPException(status_code=400, detail="Solde HTG insuffisant")
        user.wallet.htg = float(user.wallet.htg) - amt
    else:
        if float(user.wallet.usd) < amt:
            raise HTTPException(status_code=400, detail="Solde USD insuffisant")
        user.wallet.usd = float(user.wallet.usd) - amt

    note = (data.note or "").strip()
    note2 = f"partner:{p.name} ({p.id})" + (f" | {note}" if note else "")

    tx = Transaction(
        user_id=user.id,
        type="partner_spend",
        currency=data.currency,
        amount=-amt,  # débit => négatif
        note=note2,
        direction="partner_spend",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    return PartnerSpendOut(
        ok=True,
        partner_id=p.id,
        currency=data.currency,
        amount=amt,
        new_balance_htg=float(user.wallet.htg),
        new_balance_usd=float(user.wallet.usd),
        tx_id=tx.id,
    )
