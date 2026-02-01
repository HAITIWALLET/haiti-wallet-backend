from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .db import get_db
from .models import Transaction, User
from .security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats")
def admin_stats(
    days: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # période
    since = datetime.utcnow() - timedelta(days=days)

    # revenus frais (amount est NEGATIF dans tx_fee => on prend -sum)
    fee_htg = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "fee", Transaction.currency == "htg", Transaction.created_at >= since)
        .scalar()
    )
    fee_usd = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "fee", Transaction.currency == "usd", Transaction.created_at >= since)
        .scalar()
    )

    # total spend partenaires (débit négatif)
    spend_htg = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "partner_spend", Transaction.currency == "htg", Transaction.created_at >= since)
        .scalar()
    )
    spend_usd = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "partner_spend", Transaction.currency == "usd", Transaction.created_at >= since)
        .scalar()
    )

    # volume topup net (positif)
    topup_htg = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "topup", Transaction.currency == "htg", Transaction.created_at >= since)
        .scalar()
    )
    topup_usd = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.type == "topup", Transaction.currency == "usd", Transaction.created_at >= since)
        .scalar()
    )

    return {
        "period_days": days,
        "fees": {"htg": float(-fee_htg), "usd": float(-fee_usd)},          # revenu = positif
        "spend": {"htg": float(-spend_htg), "usd": float(-spend_usd)},     # total dépensé = positif
        "topups_net": {"htg": float(topup_htg), "usd": float(topup_usd)},
    }
