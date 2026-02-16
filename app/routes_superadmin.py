from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import require_superadmin
from .schemas import UserOut, RoleUpdateIn
from .security import create_access_token

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), sa: User = Depends(require_superadmin)):
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
        created_at=u.created_at
    )
    for u in users
]


@router.post("/users/{user_id}/role", response_model=UserOut)
def set_user_role(
    user_id: int,
    data: RoleUpdateIn,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    new_role = (data.role or "").strip().lower()
    if new_role not in ("user", "admin"):
        # IMPORTANT: personne ne peut créer un superadmin via l'UI
        raise HTTPException(status_code=400, detail="Role invalide (user/admin seulement)")

    # bloque auto-downgrade si tu veux (optionnel):
    if u.id == sa.id and new_role != sa.role:
        raise HTTPException(status_code=400, detail="Impossible de modifier ton propre rôle")

    u.role = new_role
    db.commit()
    db.refresh(u)

    return UserOut(
    id=u.id,
    email=u.email,
    role=u.role,
    status=u.status,
    first_name=u.first_name,
    last_name=u.last_name,
    phone=u.phone,
    created_at=u.created_at
)

@router.delete("/superadmin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de supprimer un superadmin")

    db.delete(user)
    db.commit()

    return {"message": "Utilisateur supprimé"}

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

    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token}


@router.post("/users/{user_id}/status")
def change_status(
    user_id: int,
    status: str,
    db: Session = Depends(get_db),
    sa: User = Depends(require_superadmin),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de modifier un superadmin")

    if status not in ["active", "suspended", "banned"]:
        raise HTTPException(status_code=400, detail="Statut invalide")

    user.status = status
    db.commit()

    return {"message": f"Statut changé en {status}"}

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
