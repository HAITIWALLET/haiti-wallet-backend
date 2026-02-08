from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User, Transaction
from .schemas import AdminAdjustIn, AdminAdjustOut
from .security import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/wallet/adjust", response_model=AdminAdjustOut)
def admin_adjust_wallet(
    data: AdminAdjustIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    if admin.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin requis")

    email = (data.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email requis")

    u = db.query(User).filter(User.email == email).first()
    if not u or not u.wallet:
        raise HTTPException(status_code=404, detail="Utilisateur/wallet introuvable")

    if data.currency not in ("htg", "usd"):
        raise HTTPException(status_code=400, detail="Devise invalide")

    amt = float(data.amount or 0)
    if amt == 0:
        raise HTTPException(status_code=400, detail="Montant invalide (≠ 0)")

    # apply
    if data.currency == "htg":
        u.wallet.htg = float(u.wallet.htg) + amt
        if float(u.wallet.htg) < 0:
            raise HTTPException(status_code=400, detail="Solde HTG deviendrait négatif")
    else:
        u.wallet.usd = float(u.wallet.usd) + amt
        if float(u.wallet.usd) < 0:
            raise HTTPException(status_code=400, detail="Solde USD deviendrait négatif")

    note = (data.note or "").strip()
    tx = Transaction(
        user_id=u.id,
        type="admin_adjust",
        currency=data.currency,
        amount=amt,
        note=f"admin_adjust by {admin.email}" + (f" | {note}" if note else ""),
        direction="admin_adjust",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)
    db.commit()

    return AdminAdjustOut(
        ok=True,
        email=u.email,
        currency=data.currency,
        amount=amt,
        new_balance_htg=float(u.wallet.htg),
        new_balance_usd=float(u.wallet.usd),
        tx_id=tx.id,
    )
