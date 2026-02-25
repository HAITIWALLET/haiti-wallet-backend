# app/main.py
from pathlib import Path
import os
import cloudinary
import cloudinary.uploader

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File, Depends

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from .db import Base, engine, get_db, SessionLocal
from . import models
from .models import User
from .security import hash_password, get_current_user

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


# ==============================
# CONFIG CLOUDINARY
# ==============================

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)


# ==============================
# APP
# ==============================

app = FastAPI(title="Haiti Wallet Backend")

Base.metadata.create_all(bind=engine, checkfirst=True)


# ==============================
# AUTO MIGRATION profile_image
# ==============================

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN profile_image TEXT"))
        conn.commit()
        print("profile_image column added.")
except ProgrammingError:
    print("profile_image column already exists.")


# ==============================
# SEED SUPERADMIN
# ==============================

@app.on_event("startup")
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
        print("Superadmin created")

    db.close()


# ==============================
# ROUTERS
# ==============================

app.include_router(auth_router)
app.include_router(wallet_router)
app.include_router(admin_router)
app.include_router(provider_router)
app.include_router(topups_router)
app.include_router(export_router)
app.include_router(partners_router)
app.include_router(partners_spend_router)
app.include_router(admin_stats_router)
app.include_router(wallet_spend_router)
app.include_router(admin_wallet_router)
app.include_router(admin_users_router)
app.include_router(superadmin_router)


# ==============================
# STATIC
# ==============================

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ==============================
# CLOUDINARY UPLOAD
# ==============================

@app.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = cloudinary.uploader.upload(file.file)
    image_url = result["secure_url"]

    current_user.profile_image = image_url
    db.commit()

    return {"image_url": image_url}


# ==============================
# ROOT
# ==============================

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")