from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import require_superadmin
from .schemas import UserOut, RoleUpdateIn
from security import create_access_token
from routes_auth import get_current_superadmin

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), sa: User = Depends(require_superadmin)):
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        UserOut(id=u.id, email=u.email, role=u.role, created_at=getattr(u, "created_at", None))
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

    return UserOut(id=u.id, email=u.email, role=u.role, created_at=getattr(u, "created_at", None))

@router.delete("/superadmin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible de supprimer un superadmin")

    db.delete(user)
    db.commit()

    return {"message": "Utilisateur supprimé"}

@router.post("/superadmin/users/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superadmin)
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Impossible d'impersoner un superadmin")

    access_token = create_access_token(
        data={"sub": user.email}
    )

    return {"access_token": access_token}
