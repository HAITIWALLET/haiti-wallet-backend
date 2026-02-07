from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .models import Transaction
from .security import require_admin, require_superadmin

router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"]
)

# ======================================================
# SUPERADMIN — liste utilisateurs (vue gouvernance)
# ======================================================
@router.get("", response_model=list[dict])
def list_users_superadmin(
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    rows = (
        db.query(User)
        .order_by(User.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "status": u.status,
        }
        for u in rows
    ]


# ======================================================
# ADMIN — liste utilisateurs (vue opérationnelle)
# ======================================================
@router.get("/users", response_model=list[dict])
def list_users_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = db.query(User).order_by(User.id.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "status": u.status,
        }
        for u in rows
    ]


# ======================================================
# ADMIN — changer le status d’un utilisateur
# active | suspended | banned
# ======================================================
@router.post("/users/{user_id}/status")
def change_user_status(
    user_id: int,
    status: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if status not in ["active", "suspended", "banned"]:
        raise HTTPException(status_code=400, detail="Status invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.status = status
    db.commit()

    return {
        "ok": True,
        "user_id": user.id,
        "status": user.status,
    }


# ======================================================
# SUPERADMIN — changer le rôle d’un utilisateur
# user <-> admin
# ======================================================
@router.post("/users/{user_id}/role")
def set_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    if role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Role invalide")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(
            status_code=400,
            detail="Impossible de modifier un superadmin"
        )

    user.role = role
    db.commit()

    return {
        "ok": True,
        "user_id": user.id,
        "role": user.role,
    }

@router.get("/users/{user_id}/wallet")
def admin_view_user_wallet(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")

    if not user.wallet:
        return {
            "user_id": user.id,
            "wallet": None,
            "transactions": []
        }

    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .limit(200)
        .all()
    )

    return {
        "user_id": user.id,
        "email": user.email,
        "status": user.status,
        "role": user.role,
        "wallet": {
            "htg": user.wallet.htg,
            "usd": user.wallet.usd,
        },
        "transactions": [
            {
                "id": tx.id,
                "type": tx.type,
                "currency": tx.currency,
                "amount": tx.amount,
                "note": tx.note,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ]
    }
