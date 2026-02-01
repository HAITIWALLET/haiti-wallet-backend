# app/make_admin.py
from sqlalchemy.orm import Session

from .db import SessionLocal, Base, engine
from .models import User, Wallet
from .security import hash_password

ADMIN_EMAIL = "admin@haiti.com"
ADMIN_PASSWORD = "admin123"

def main():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    email = ADMIN_EMAIL.lower().strip()
    u = db.query(User).filter(User.email == email).first()

    if not u:
        u = User(
            email=email,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",  # ✅ IMPORTANT
        )
        u.wallet = Wallet(htg=0.0, usd=0.0)
        db.add(u)
        db.commit()
        db.refresh(u)
        print(f"OK admin créé: {ADMIN_EMAIL} mdp={ADMIN_PASSWORD}")
        return

    # ✅ SI l'utilisateur existe déjà, on le “promote” admin
    u.role = "admin"
    # (optionnel) reset password si tu veux:
    u.password_hash = hash_password(ADMIN_PASSWORD)

    # wallet si jamais manquant
    if not getattr(u, "wallet", None):
        u.wallet = Wallet(htg=0.0, usd=0.0)

    db.commit()
    print(f"OK admin mis à jour: {ADMIN_EMAIL} mdp={ADMIN_PASSWORD}")

if __name__ == "__main__":
    main()
