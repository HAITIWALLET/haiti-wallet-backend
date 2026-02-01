from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from .db import get_db
from .models import User, Transaction, FxSetting
from .schemas import WalletOut, TransferIn, ConvertIn, ConvertOut, TxOut
from .security import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


def get_fx(db: Session) -> FxSetting:
    fx = db.query(FxSetting).first()
    if not fx:
        fx = FxSetting(sell_usd=134.0, buy_usd=126.0)
        db.add(fx)
        db.commit()
        db.refresh(fx)
    return fx


@router.get("", response_model=WalletOut)
def get_wallet(user: User = Depends(get_current_user)):
    return user.wallet


@router.get("/transactions", response_model=list[TxOut])
def transactions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.id.desc()).all()
    return rows


@router.post("/transfer")
def transfer(data: TransferIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    to_email = data.to_email.lower().strip()
    if to_email == user.email:
        raise HTTPException(status_code=400, detail="Transfert vers soi-même interdit")

    dest = db.query(User).filter(User.email == to_email).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destinataire introuvable")

    amt = float(data.amount)
    cur = data.currency

    if cur == "htg":
        if user.wallet.htg < amt:
            raise HTTPException(status_code=400, detail="Solde HTG insuffisant")
        user.wallet.htg -= amt
        dest.wallet.htg += amt
    else:
        if user.wallet.usd < amt:
            raise HTTPException(status_code=400, detail="Solde USD insuffisant")
        user.wallet.usd -= amt
        dest.wallet.usd += amt

    db.add(Transaction(
        user_id=user.id, type="transfer", currency=cur, amount=amt,
        note=data.note or "transfer", direction="transfer_out", rate_used=None, created_at=datetime.utcnow()
    ))
    db.add(Transaction(
        user_id=dest.id, type="transfer", currency=cur, amount=amt,
        note=data.note or "transfer", direction="transfer_in", rate_used=None, created_at=datetime.utcnow()
    ))

    db.commit()
    return {"ok": True}


@router.post("/convert", response_model=ConvertOut)
def convert(data: ConvertIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fx = get_fx(db)
    amt = float(data.amount)

    if data.direction == "htg_to_usd":
        if user.wallet.htg < amt:
            raise HTTPException(status_code=400, detail="Solde HTG insuffisant")
        rate = float(fx.sell_usd)
        out = amt / rate
        user.wallet.htg -= amt
        user.wallet.usd += out

        db.add(Transaction(
            user_id=user.id, type="convert", currency="htg", amount=amt,
            note="HTG->USD", direction="htg_to_usd", rate_used=rate, created_at=datetime.utcnow()
        ))
        db.commit()
        return ConvertOut(from_currency="htg", to_currency="usd", amount_in=amt, amount_out=out, rate_used=rate)

    else:
        if user.wallet.usd < amt:
            raise HTTPException(status_code=400, detail="Solde USD insuffisant")
        rate = float(fx.buy_usd)
        out = amt * rate
        user.wallet.usd -= amt
        user.wallet.htg += out

        db.add(Transaction(
            user_id=user.id, type="convert", currency="usd", amount=amt,
            note="USD->HTG", direction="usd_to_htg", rate_used=rate, created_at=datetime.utcnow()
        ))
        db.commit()
        return ConvertOut(from_currency="usd", to_currency="htg", amount_in=amt, amount_out=out, rate_used=rate)
