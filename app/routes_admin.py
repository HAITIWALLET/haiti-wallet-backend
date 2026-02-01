from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from .db import get_db
from .models import FxSetting, User, Transaction
from .schemas import FxIn, FxOut
from .security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


# -------------------------
# FX
# -------------------------
@router.get("/fx", response_model=FxOut)
def get_fx(db: Session = Depends(get_db), admin=Depends(require_admin)):
    fx = db.query(FxSetting).first()
    if not fx:
        fx = FxSetting(sell_usd=134.0, buy_usd=126.0)
        db.add(fx)
        db.commit()
        db.refresh(fx)
    return FxOut(sell_usd=fx.sell_usd, buy_usd=fx.buy_usd)


@router.post("/fx", response_model=FxOut)
def set_fx(data: FxIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    fx = db.query(FxSetting).first()
    if not fx:
        fx = FxSetting()
        db.add(fx)
    fx.sell_usd = float(data.sell_usd)
    fx.buy_usd = float(data.buy_usd)
    db.commit()
    return FxOut(sell_usd=fx.sell_usd, buy_usd=fx.buy_usd)


# =========================================================
# ADMIN — WALLET ADJUST (Débiter / Créditer)
# POST /admin/wallet/adjust
# =========================================================

class WalletAdjustIn(BaseModel):
    email: EmailStr
    currency: str = Field(..., description="htg or usd")
    amount: float = Field(..., description="Positive=credit, Negative=debit")
    note: str | None = None


class WalletAdjustOut(BaseModel):
    email: EmailStr
    currency: str
    amount: float
    new_balance_htg: float
    new_balance_usd: float
    tx_id: int | None = None


@router.post("/wallet/adjust", response_model=WalletAdjustOut)
def admin_wallet_adjust(
    data: WalletAdjustIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    currency = (data.currency or "").lower().strip()
    if currency not in ("htg", "usd"):
        raise HTTPException(status_code=400, detail="Devise invalide (htg/usd)")

    amount = float(data.amount or 0)
    if amount == 0:
        raise HTTPException(status_code=400, detail="Montant invalide (≠ 0)")

    u = db.query(User).filter(User.email == str(data.email)).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Sécurité: empêche solde négatif
    if currency == "htg":
        current = float(u.wallet.htg or 0)
        new_val = current + amount
        if new_val < 0:
            raise HTTPException(status_code=400, detail="Solde HTG insuffisant pour débiter")
        u.wallet.htg = new_val
    else:
        current = float(u.wallet.usd or 0)
        new_val = current + amount
        if new_val < 0:
            raise HTTPException(status_code=400, detail="Solde USD insuffisant pour débiter")
        u.wallet.usd = new_val

    # Audit: transaction "admin_adjust"
    # (si tes champs Transaction diffèrent, je l'adapte)
    tx = Transaction(
        user_id=u.id,
        type="admin_adjust",
        currency=currency,
        amount=abs(amount),
        note=data.note or ("Crédit admin" if amount > 0 else "Débit admin"),
        direction="admin_credit" if amount > 0 else "admin_debit",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)

    db.commit()
    db.refresh(tx)
    db.refresh(u)

    return WalletAdjustOut(
        email=u.email,
        currency=currency,
        amount=amount,
        new_balance_htg=float(u.wallet.htg or 0),
        new_balance_usd=float(u.wallet.usd or 0),
        tx_id=getattr(tx, "id", None),
    )
