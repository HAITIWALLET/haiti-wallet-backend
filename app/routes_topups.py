from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import TopupRequest, User, Transaction, Wallet
from .schemas import TopupRequestIn, TopupRequestOut, TopupDecisionIn
from .security import get_current_user, require_admin
from .Services.fees import compute_fee, net_amount

router = APIRouter(prefix="/topups", tags=["topups"])


# -------------------------
# FEES (fixed, same numbers for HTG and USD)
# -------------------------
def calc_fee(amount: float) -> float:
    a = float(amount or 0)
    if a <= 20:
        return 1.50
    if a <= 50:
        return 3.00
    if a <= 70:
        return 5.00
    return 7.50


def _to_out(req: TopupRequest, user_email: str) -> TopupRequestOut:
    return TopupRequestOut(
        id=req.id,
        user_id=req.user_id,
        user_email=user_email,
        amount=float(req.amount),
        fee_amount=float(getattr(req, "fee_amount", 0.0)),
        net_amount=float(getattr(req, "net_amount", float(req.amount))),
        currency=req.currency,
        method=req.method,
        reference=req.reference,
        proof_url=req.proof_url,
        note=req.note,
        status=req.status,
        admin_note=req.admin_note,
        created_at=req.created_at,
        decided_at=req.decided_at,
    )


@router.post("/request", response_model=TopupRequestOut)
def create_request(
    data: TopupRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fee_check = calc_fee(float(data.amount))
    if float(data.amount) <= fee_check:
        raise HTTPException(
            status_code=400,
            detail=f"Montant trop faible. Frais = {fee_check} {data.currency}.",
        )

    fee = compute_fee(float(data.amount))
    net = net_amount(float(data.amount))

    req = TopupRequest(
        user_id=user.id,
        amount=float(data.amount),
        fee_amount=float(fee),
        net_amount=float(net),
        currency=data.currency,
        method=data.method,
        reference=data.reference,
        proof_url=data.proof_url,
        note=data.note,
        status="PENDING",
        admin_note=None,
        created_at=datetime.utcnow(),
        decided_at=None,
    )

    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_out(req, user.email)


@router.get("/mine", response_model=list[TopupRequestOut])
def my_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(TopupRequest)
        .filter(TopupRequest.user_id == user.id)
        .order_by(TopupRequest.id.desc())
        .all()
    )
    return [_to_out(r, user.email) for r in rows]


@router.get("/pending", response_model=list[TopupRequestOut])
def pending_requests(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        db.query(TopupRequest, User.email)
        .join(User, User.id == TopupRequest.user_id)
        .filter(TopupRequest.status == "PENDING")
        .order_by(TopupRequest.id.asc())
        .all()
    )
    return [_to_out(r, email) for (r, email) in rows]


@router.post("/{req_id}/decide")
def decide_request(
    req_id: int,
    data: TopupDecisionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = db.query(TopupRequest).filter(TopupRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable")

    # 🔒 ADMIN ne peut PAS approuver sa propre demande
    if admin.role == "admin" and req.user_id == admin.id:
        raise HTTPException(
            status_code=403,
            detail="Un admin ne peut pas approuver sa propre demande"
        )

    if req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Demande déjà traitée")

    decision = (data.decision or "").upper()

    u = db.query(User).filter(User.id == req.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    wallet = db.query(Wallet).filter(Wallet.user_id == u.id).first()
    if not wallet:
        raise HTTPException(status_code=500, detail="Wallet introuvable")

    fee = float(req.fee_amount or 0)
    net = float(req.net_amount or req.amount)

    if decision == "APPROVED":
        req.status = "APPROVED"
        req.decided_at = datetime.utcnow()
        req.admin_note = data.admin_note

        if req.currency.lower() == "htg":
            wallet.htg += net
        elif req.currency.lower() == "usd":
            wallet.usd += net
        else:
            raise HTTPException(status_code=400, detail="Devise invalide")

        tx_topup = Transaction(
            user_id=u.id,
            type="topup",
            currency=req.currency,
            amount=net,
            note=f"Recharge approuvée ({req.method}) ref:{req.reference}",
            direction="manual_topup",
            rate_used=None,
            created_at=datetime.utcnow(),
        )
        db.add(tx_topup)

        if fee > 0:
            tx_fee = Transaction(
                user_id=u.id,
                type="fee",
                currency=req.currency,
                amount=fee,
                note="Frais Haiti Wallet",
                direction="fee",
                rate_used=None,
                created_at=datetime.utcnow(),
            )
            db.add(tx_fee)

        apply_referral_bonus_one_shot(db, u)

    elif decision == "REJECTED":
        req.status = "REJECTED"
        req.decided_at = datetime.utcnow()
        req.admin_note = data.admin_note

    else:
        raise HTTPException(status_code=400, detail="Décision invalide")

    db.commit()
    db.refresh(req)

    return {
        "ok": True,
        "status": req.status,
        "approved_by": admin.email,
    }


def apply_referral_bonus_one_shot(db: Session, referred_user: User):
    if not referred_user.referred_by_user_id:
        return

    referrer = db.query(User).filter(User.id == referred_user.referred_by_user_id).first()
    if not referrer:
        return

    if int(getattr(referrer, "referral_bonus_paid", 0) or 0) == 1:
        return

    children = db.query(User).filter(User.referred_by_user_id == referrer.id).all()
    if not children:
        return

    child_ids = [c.id for c in children]

    qualified = (
        db.query(TopupRequest.user_id)
        .filter(TopupRequest.user_id.in_(child_ids))
        .filter(TopupRequest.status == "APPROVED")
        .filter(TopupRequest.currency == "htg")
        .filter(TopupRequest.amount >= 250.0)
        .distinct()
        .all()
    )

    if len(qualified) < 3:
        return

    bonus = 500.0
    referrer.wallet.htg += bonus
    referrer.referral_bonus_paid = 1

    tx = Transaction(
        user_id=referrer.id,
        type="referral_bonus",
        currency="htg",
        amount=bonus,
        note="Bonus parrainage: 3 filleuls qualifiés (+500 HTG)",
        direction="referral_bonus",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)
