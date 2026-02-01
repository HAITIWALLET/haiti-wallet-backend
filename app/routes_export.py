# app/routes_export.py
from datetime import datetime
import csv
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .db import get_db
from .security import get_current_user
from .models import User, Transaction

router = APIRouter(prefix="/export", tags=["export"])


def _dt(v: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string like 2026-01-27T12:30:00 or date 2026-01-27."""
    if not v:
        return None
    try:
        # support date only
        if len(v) == 10:
            return datetime.fromisoformat(v + "T00:00:00")
        return datetime.fromisoformat(v)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Date invalide: {v} (format ISO attendu)")


def _tx_to_row(tx: Transaction, user_email: str) -> list:
    created = tx.created_at.isoformat() if tx.created_at else ""
    return [
        tx.id,
        user_email,
        tx.type,
        tx.currency,
        float(tx.amount),
        tx.note or "",
        tx.direction or "",
        float(tx.rate_used) if tx.rate_used is not None else "",
        created,
    ]


@router.get("/me/transactions.csv")
def export_my_transactions_csv(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    from_dt: Optional[str] = Query(None, description="ISO datetime ou date (YYYY-MM-DD)"),
    to_dt: Optional[str] = Query(None, description="ISO datetime ou date (YYYY-MM-DD)"),
) -> Response:
    """User export: only his transactions."""
    f = _dt(from_dt)
    t = _dt(to_dt)

    q = db.query(Transaction).filter(Transaction.user_id == me.id)
    if f:
        q = q.filter(Transaction.created_at >= f)
    if t:
        q = q.filter(Transaction.created_at <= t)

    q = q.order_by(Transaction.created_at.desc(), Transaction.id.desc())
    rows = q.all()

    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "user_email", "type", "currency", "amount", "note", "direction", "rate_used", "created_at"])
    for tx in rows:
        w.writerow(_tx_to_row(tx, me.email))

    filename = f"transactions_{me.email}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/transactions.csv")
def export_admin_transactions_csv(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
    user_email: Optional[str] = Query(None, description="Filtrer sur un email"),
    tx_type: Optional[str] = Query(None, description="Ex: transfer, convert, topup_request, topup_approved, ..."),
    currency: Optional[str] = Query(None, description="htg ou usd"),
    from_dt: Optional[str] = Query(None, description="ISO datetime ou date (YYYY-MM-DD)"),
    to_dt: Optional[str] = Query(None, description="ISO datetime ou date (YYYY-MM-DD)"),
    limit: int = Query(5000, ge=1, le=50000),
) -> Response:
    """Admin export: all transactions, optional filters."""
    if me.role != "admin":
        raise HTTPException(status_code=403, detail="Accès admin requis")

    f = _dt(from_dt)
    t = _dt(to_dt)

    q = db.query(Transaction, User.email).join(User, User.id == Transaction.user_id)

    if user_email:
        q = q.filter(User.email == user_email.strip().lower())
    if tx_type:
        q = q.filter(Transaction.type == tx_type.strip())
    if currency:
        q = q.filter(Transaction.currency == currency.strip().lower())
    if f:
        q = q.filter(Transaction.created_at >= f)
    if t:
        q = q.filter(Transaction.created_at <= t)

    q = q.order_by(Transaction.created_at.desc(), Transaction.id.desc()).limit(limit)
    rows = q.all()

    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "user_email", "type", "currency", "amount", "note", "direction", "rate_used", "created_at"])
    for tx, email in rows:
        w.writerow(_tx_to_row(tx, email))

    filename = f"transactions_ALL_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
