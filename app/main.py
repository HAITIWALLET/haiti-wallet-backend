# app/main.py
from pathlib import Path
import os

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

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# ---- Auto migration profile_image ----
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN profile_image TEXT"))
        conn.commit()
        print("profile_image column added.")
except ProgrammingError:
    print("profile_image column already exists.")

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .db import SessionLocal
from .models import User, Wallet
from .security import hash_password


@ app.on_event("startup")
def seed_superadmin():
    db = SessionLocal()

    email = "adminndk@haiti.com"
    password = "@Haitiwallet20-26"

    existing = db.query(User).filter(User.email == email).first()

    if not existing:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role="superadmin",
            status="active"
        )
        db.add(user)
        db.commit()
        print("✅ Superadmin seed créé")

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

from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
import os
import shutil

# Dossier uploads
upload_dir = Path(__file__).resolve().parent / "uploads"
upload_dir.mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

from fastapi import Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.security import get_current_user

@app.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = f"user_{current_user.id}.jpg"
    file_path = upload_dir / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"/uploads/{filename}"

    current_user.profile_picture = image_url
    db.commit()

    return {"image_url": image_url}

# Root -> UI
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")
