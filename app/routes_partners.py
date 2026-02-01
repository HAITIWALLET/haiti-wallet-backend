# app/routes_partners.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Partner
from .schemas import PartnerIn, PartnerOut
from .security import get_current_user

router = APIRouter(prefix="/partners", tags=["partners"])

def require_admin(user):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin seulement")

# PUBLIC: liste des partenaires actifs (pour users)
@router.get("", response_model=list[PartnerOut])
def list_partners(db: Session = Depends(get_db)):
    return db.query(Partner).filter(Partner.active == True).order_by(Partner.id.desc()).all()

# ADMIN: liste complète (actifs + inactifs)
@router.get("/admin", response_model=list[PartnerOut])
def list_partners_admin(db: Session = Depends(get_db), me=Depends(get_current_user)):
    require_admin(me)
    return db.query(Partner).order_by(Partner.id.desc()).all()

# ADMIN: créer partenaire
@router.post("", response_model=PartnerOut)
def create_partner(payload: PartnerIn, db: Session = Depends(get_db), me=Depends(get_current_user)):
    require_admin(me)

    p = Partner(
        name=payload.name.strip(),
        category=(payload.category or "autre").strip(),
        url=payload.url.strip(),
        description=(payload.description.strip() if payload.description else None),
        logo_url=(payload.logo_url.strip() if payload.logo_url else None),
        active=bool(payload.active),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

# ADMIN: activer/désactiver
@router.post("/{partner_id}/active", response_model=PartnerOut)
def set_partner_active(partner_id: int, active: bool, db: Session = Depends(get_db), me=Depends(get_current_user)):
    require_admin(me)

    p = db.query(Partner).filter(Partner.id == partner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Partenaire introuvable")

    p.active = bool(active)
    db.commit()
    db.refresh(p)
    return p
