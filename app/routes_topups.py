from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import TopupRequest, User, Transaction
from .schemas import TopupRequestIn, TopupRequestOut, TopupDecisionIn
from .security import get_current_user, require_admin
from .Services.fees import compute_fee, net_amount

router = APIRouter(prefix="/topups", tags=["topups"])


# -------------------------
# FEES (fixed, same numbers for HTG and USD)
# -------------------------
def calc_fee(amount: float) -> float:
    """
    Barème (identique HTG et USD, sans conversion):
    0–20  -> 1.50
    21–50 -> 3.00
    51–70 -> 5.00
    71+   -> 7.50
    """
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
    # ✅ validate fee vs amount
    fee_check = calc_fee(float(data.amount))
    if float(data.amount) <= fee_check:
        raise HTTPException(
            status_code=400,
            detail=f"Montant trop faible. Frais = {fee_check} {data.currency}.",
        )

    # Crée une demande PENDING (safe, manuel)
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


@router.post("/{req_id}/decide", response_model=TopupRequestOut)
def decide_request(
    req_id: int,
    data: TopupDecisionIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = db.query(TopupRequest).filter(TopupRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if req.status != "PENDING":
        raise HTTPException(status_code=400, detail="Déjà traitée")

    u = db.query(User).filter(User.id == req.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    status = (data.status or "").upper()
    if status not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Statut invalide")

    # Applique décision
    req.status = status
    req.admin_note = data.admin_note
    req.decided_at = datetime.utcnow()

    if status == "APPROVED":
        fee = float(getattr(req, "fee_amount", 0.0))
        net = float(getattr(req, "net_amount", float(req.amount)))

        # créditer wallet (NET)
        if req.currency == "htg":
            u.wallet.htg = float(u.wallet.htg) + net
        else:
            u.wallet.usd = float(u.wallet.usd) + net

        # -------------------------
        # PARRAINAGE: bonus 500 HTG une seule fois
        # Conditions:
        # - l'utilisateur a un referred_by
        # - recharge HTG >= 250 (ou USD >= équivalent si tu veux; sinon HTG seulement)
        # - pas encore récompensé (ref_rewarded == False)
        # - le parrain doit exister
        # - "3 inscrits" : on compte les success_count
        # -------------------------
        try:
            if getattr(u, "referred_by", None) and not getattr(u, "ref_rewarded", False):
                # on impose condition HTG min 250 (clair)
                if req.currency == "htg" and float(req.amount) >= 250:
                    referrer = db.query(User).filter(User.ref_code == u.referred_by).first()
                    if referrer:
                        # incrémenter succès parrain
                        referrer.ref_success_count = int(getattr(referrer, "ref_success_count", 0)) + 1

                        # si atteint 3 -> donner 500 HTG et marquer ref_rewarded pour CE user (ou pour le referrer)
                        # Ici: tu veux 500 HTG au parrain après 3 succès.
                        if referrer.ref_success_count >= 3:
                            referrer.wallet.htg += 500.0

                            tx_bonus = Transaction(
                                user_id=referrer.id,
                                type="referral_bonus",
                                currency="htg",
                                amount=500.0,
                                note="Bonus parrainage: 3 filleuls + recharge min 250 HTG",
                                direction="referral_bonus",
                                rate_used=None,
                                created_at=datetime.utcnow(),
                            )
                            db.add(tx_bonus)

                        # marquer ce filleul comme “a servi” (une seule fois)
                        u.ref_rewarded = True

                        db.add(referrer)
                        db.add(u)
                        db.commit()
        except Exception:
            # en dev: tu peux print/log l'erreur
            pass

        # Transaction TOPUP (NET)
        tx_topup = Transaction(
            user_id=u.id,
            type="topup",
            currency=req.currency,
            amount=net,
            note=f"Topup approuvé (net) via {req.method} ref:{req.reference}",
            direction="manual_topup",
            rate_used=None,
            created_at=datetime.utcnow(),
        )
        db.add(tx_topup)

        # Transaction FEES (audit)
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
    db.commit()


    # ✅ IMPORTANT: commit + refresh + return (sinon 500)
    db.commit()
    db.refresh(req)

    # récupère email pour la réponse
    email = u.email if u else ""
    return _to_out(req, email)

def apply_referral_bonus_one_shot(db: Session, referred_user: User):
    # doit avoir un parrain
    if not referred_user.referred_by_user_id:
        return

    referrer = db.query(User).filter(User.id == referred_user.referred_by_user_id).first()
    if not referrer:
        return

    # ✅ déjà payé -> stop
    if int(getattr(referrer, "referral_bonus_paid", 0) or 0) == 1:
        return

    # récupérer tous les filleuls
    children = db.query(User).filter(User.referred_by_user_id == referrer.id).all()
    if not children:
        return
    child_ids = [c.id for c in children]

    # compter les filleuls qualifiés
    qualified_child_ids = (
        db.query(TopupRequest.user_id)
        .filter(TopupRequest.user_id.in_(child_ids))
        .filter(TopupRequest.status == "APPROVED")
        .filter(TopupRequest.currency == "htg")
        .filter(TopupRequest.amount >= 250.0)
        .distinct()
        .all()
    )
    qualified_count = len(qualified_child_ids)

    if qualified_count < 3:
        return

    # ✅ payer une seule fois
    bonus = 500.0
    referrer.wallet.htg += bonus
    referrer.referral_bonus_paid = 1

    tx = Transaction(
        user_id=referrer.id,
        type="referral_bonus",
        currency="htg",
        amount=bonus,
        note="Bonus parrainage: 3 filleuls qualifiés (+500 HTG) — payé une fois",
        direction="referral_bonus",
        rate_used=None,
        created_at=datetime.utcnow(),
    )
    db.add(tx)
