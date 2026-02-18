from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import require_superadmin, create_access_token
from .schemas import UserOut, RoleUpdateIn

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


# =========================================================
# LIST USERS
# =========================================================

@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    users = db.query(User).order_by(User.id.asc()).all()

    return [
        UserOut(
            id=u.id,
            email=u.email,
            role=u.role,
            status=u.status,
            first_name=u.first_name,
            last_name=u.last_name,
            phone=u.phone,
            created_at=u.created_at,
        )
        for u in users
    ]


# =========================================================
# CHANGE ROLE
# =========================================================

@router.post("/users/{user_id}/role", response_model=UserOut)
def set_user_role(
    user_id: int,
    data: RoleUpdateIn,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de modifier un superadmin")

    new_role = (data.role or "").strip().lower()

    if new_role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Role invalide")

    user.role = new_role
    db.commit()
    db.refresh(user)

    return user


# =========================================================
# CHANGE STATUS
# =========================================================

from pydantic import BaseModel

class StatusUpdate(BaseModel):
    status: str


@router.post("/users/{user_id}/status")
def change_status(
    user_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de modifier un superadmin")

    if data.status not in ["active", "suspended", "banned"]:
        raise HTTPException(status_code=400, detail="Statut invalide")

    user.status = data.status
    db.commit()

    return {"message": f"Statut changé en {data.status}"}



# =========================================================
# DELETE USER
# =========================================================

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de supprimer un superadmin")

    db.delete(user)
    db.commit()

    return {"message": "Utilisateur supprimé"}


# =========================================================
# IMPERSONATE
# =========================================================

@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible d'impersoner un superadmin")

    access_token = create_access_token({"sub": user.email})

    return {"access_token": access_token}
