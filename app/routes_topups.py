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
# FEES (fixed)
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
        fee_amount=float(req.fee_amount or 0),
        net_amount=float(req.net_amount or req.amount),
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


# -------------------------
# CREATE REQUEST
# -------------------------
@router.post("/request", response_model=TopupRequestOut)
def create_request(
    data: TopupRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fee_check = calc_fee(float(data.amount))
    if float(data.amount) <= fee_check:
        raise HTTPException(400, "Montant trop faible")

    fee = compute_fee(float(data.amount))
    net = net_amount(float(data.amount))

    req = TopupRequest(
        user_id=user.id,
        amount=float(data.amount),
        fee_amount=fee,
        net_amount=net,
        currency=data.currency,
        method=data.method,
        reference=data.reference,
        proof_url=data.proof_url,
        note=data.note,
        status="PENDING",
        created_at=datetime.utcnow(),
    )

    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_out(req, user.email)


# -------------------------
# MY REQUESTS
# -------------------------
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


# -------------------------
# PENDING (ADMIN)
# -------------------------
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


# -------------------------
# DECIDE REQUEST (FIXED)
# -------------------------
@router.post("/{req_id}/decide")
def decide_request(
    req_id: int,
    data: TopupDecisionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # 1️⃣ Récupérer la demande
    req = db.query(TopupRequest).filter(TopupRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable")

    # 2️⃣ Admin ne peut PAS approuver sa propre recharge
    if admin.role == "admin" and req.user_id == admin.id:
        raise HTTPException(
            status_code=403,
            detail="Un admin ne peut pas approuver sa propre recharge",
        )

    # 3️⃣ Déjà traitée
    if req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Demande déjà traitée")

    # 4️⃣ 🔥 BUG FIX MAJEUR — on lit BIEN status
    decision = (data.status or "").upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Décision invalide")

    req.status = decision
    req.approved_by = admin.id
    req.decided_at = datetime.utcnow()

    # 5️⃣ APPROVED → créditer le wallet
    if decision == "APPROVED":
        wallet = db.query(Wallet).filter(Wallet.user_id == req.user_id).first()

        # 🔥 BUG FIX — créer le wallet s’il n’existe pas
        if not wallet:
            wallet = Wallet(
                user_id=req.user_id,
                htg=0.0,
                usd=0.0,
                created_at=datetime.utcnow(),
            )
            db.add(wallet)
            db.flush()  # PAS de commit ici

        if req.currency.lower() == "htg":
            wallet.htg += req.net_amount
        elif req.currency.lower() == "usd":
            wallet.usd += req.net_amount
        else:
            raise HTTPException(status_code=400, detail="Devise invalide")

        # Transaction TOPUP
        tx = Transaction(
            user_id=req.user_id,
            type="topup",
            currency=req.currency,
            amount=req.net_amount,
            note=f"Topup approuvé ({req.method})",
            direction="manual_topup",
            created_at=datetime.utcnow(),
        )
        db.add(tx)

    db.commit()
    db.refresh(req)

    return {"ok": True, "status": req.status}

