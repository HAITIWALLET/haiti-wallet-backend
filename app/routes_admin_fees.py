from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .db import get_db
from .models import Transaction, User
from .security import require_admin

router = APIRouter(prefix="/admin/fees", tags=["admin"])

@router.get("/stats")
def fees_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # total par devise
    rows = (
        db.query(Transaction.currency, func.sum(Transaction.amount))
        .filter(Transaction.type == "fee")
        .group_by(Transaction.currency)
        .all()
    )
    totals = {cur: float(total or 0) for (cur, total) in rows}
    return {"totals": totals}
