# app/make_admin.py
import os
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.db import SessionLocal, Base, engine
from app.models import User, Wallet
from app.security import hash_password

# 🔐 Charger .env
load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_INITIAL_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD")

if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_INITIAL_EMAIL ou ADMIN_INITIAL_PASSWORD manquant")

def main():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    email = ADMIN_EMAIL.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            email=email,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="superadmin",
            status="active",
        )
        user.wallet = Wallet(htg=0.0, usd=0.0)
        db.add(user)
        db.commit()
        print(f"✅ Superadmin créé : {email}")
        return

    # 🔁 Mise à jour sécurité
    user.role = "superadmin"
    user.status = "active"
    user.password_hash = hash_password(ADMIN_PASSWORD)

    if not getattr(user, "wallet", None):
        user.wallet = Wallet(htg=0.0, usd=0.0)

    db.commit()
    print(f"♻️ Superadmin mis à jour : {email}")

if __name__ == "__main__":
    main()
