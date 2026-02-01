from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import require_superadmin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

@router.get("", response_model=list[dict])
def list_users(db: Session = Depends(get_db), sa=Depends(require_superadmin)):
    rows = db.query(User).order_by(User.id.desc()).limit(200).all()
    return [{"id": u.id, "email": u.email, "role": u.role} for u in rows]

@router.post("/{user_id}/role")
def set_role(user_id: int, role: str, db: Session = Depends(get_db), sa=Depends(require_superadmin)):
    if role not in ("user", "admin"):
        # Important: on évite que superadmin se “multiplie”
        raise HTTPException(status_code=400, detail="Role invalide")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if u.role == "superadmin":
        raise HTTPException(status_code=400, detail="Impossible de modifier le superadmin")
    u.role = role
    db.commit()
    return {"ok": True, "user_id": u.id, "role": u.role}
