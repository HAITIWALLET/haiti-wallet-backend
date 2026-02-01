# app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from . import models  # noqa: F401  (force import models / mappings)

from .routes_auth import router as auth_router
from .routes_wallet import router as wallet_router
from .routes_admin import router as admin_router
from .routes_provider_sim import router as provider_router
from .routes_topups import router as topups_router
from .routes_export import router as export_router
from .routes_partners import router as partners_router
from .routes_partners_spend import router as partners_spend_router
from .routes_admin_stats import router as admin_stats_router
from .routes_wallet_spend import router as wallet_spend_router
from .routes_admin_wallet import router as admin_wallet_router
from .routes_admin_users import router as admin_users_router
from .routes_superadmin import router as superadmin_router


app = FastAPI(title="Haiti Wallet Backend")

# DB tables
Base.metadata.create_all(bind=engine, checkfirst=True)

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .db import SessionLocal
from .models import User, Wallet
from .security import hash_password


@app.on_event("startup")
def seed_superadmin():
    db: Session = SessionLocal()
    try:
        email = "admin@haiti.com"

        # ✅ Important: si la DB est en retard (colonnes manquantes), on ne bloque pas le démarrage
        try:
            existing = db.query(User).filter(User.email == email).first()
        except OperationalError as e:
            print("⚠️ DB pas prête / colonnes manquantes (migration requise). Seed ignoré.")
            print("   Détail:", str(e))
            return

        if not existing:
            # ✅ créer superadmin avec les champs minimaux sûrs
            u = User(
                email=email,
                password_hash=hash_password("admin1234"),  # change après
                role="superadmin",
            )

            # ✅ si ton modèle User contient d'autres champs (ref_code, phone, etc.)
            # on ne les force PAS ici pour ne pas casser (ils seront gérés par /auth/register ou /auth/phone/verify_register)

            db.add(u)
            db.commit()
            db.refresh(u)

            # wallet auto
            db.add(Wallet(user_id=u.id, htg=0.0, usd=0.0))
            db.commit()
            print("✅ Superadmin créé:", email, "pass=admin1234")
    finally:
        db.close()


# Routers
app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(admin_router)
app.include_router(provider_router)        # provider (simulation)
app.include_router(topups_router)          # topups (manual)
app.include_router(export_router)
app.include_router(partners_router)
app.include_router(partners_spend_router)
app.include_router(admin_stats_router)
app.include_router(wallet_spend_router)
app.include_router(admin_wallet_router)
app.include_router(admin_users_router)
app.include_router(superadmin_router)

# Static
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Root -> UI
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")
