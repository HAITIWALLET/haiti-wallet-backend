from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from .db import get_db
from .models import TopupRequest, User
from .security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def revenue_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    today = datetime.utcnow().date()
    now = datetime.utcnow()

    # -------------------------
    # TOTAL CUMULÉ (APPROVED)
    # -------------------------
    total = (
        db.query(func.coalesce(func.sum(TopupRequest.fee_amount), 0))
        .filter(
            TopupRequest.status == "APPROVED",
            TopupRequest.decided_at != None
        )
        .scalar()
    )

    # -------------------------
    # REVENUS AUJOURD’HUI
    # -------------------------
    today_sum = (
        db.query(func.coalesce(func.sum(TopupRequest.fee_amount), 0))
        .filter(
            TopupRequest.status == "APPROVED",
            TopupRequest.decided_at != None,
            func.date(TopupRequest.decided_at) == today
        )
        .scalar()
    )

    # -------------------------
    # REVENUS CE MOIS
    # -------------------------
    month_sum = (
        db.query(func.coalesce(func.sum(TopupRequest.fee_amount), 0))
        .filter(
            TopupRequest.status == "APPROVED",
            TopupRequest.decided_at != None,
            extract("year", TopupRequest.decided_at) == now.year,
            extract("month", TopupRequest.decided_at) == now.month
        )
        .scalar()
    )

    # -------------------------
    # GRAPH MENSUEL (12 derniers mois)
    # -------------------------
    monthly_data = []

    for i in range(12):
        month_date = now - timedelta(days=i * 30)

        month_total = (
            db.query(func.coalesce(func.sum(TopupRequest.fee_amount), 0))
            .filter(
                TopupRequest.status == "APPROVED",
                TopupRequest.decided_at != None,
                extract("year", TopupRequest.decided_at) == month_date.year,
                extract("month", TopupRequest.decided_at) == month_date.month
            )
            .scalar()
        )

        monthly_data.append({
            "year": month_date.year,
            "month": month_date.month,
            "total": float(month_total)
        })

    monthly_data.reverse()

    return {
        "today": float(today_sum),
        "month": float(month_sum),
        "total": float(total),
        "monthly": monthly_data
    }