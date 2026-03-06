# app/main.py
from pathlib import Path
import os
import uuid
import shutil

from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from fastapi.middleware.cors import CORSMiddleware

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
from .routes_merchant import router as merchant_router
from .routes_subscriptions import router as subscriptions_router
from .subscription_billing import run_subscription_billing

# ==============================
# APP
# ==============================

app = FastAPI(title="Haiti Wallet Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(merchant_router)
app.include_router(subscriptions_router)

# ==============================
# STATIC FILES
# ==============================

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


from pathlib import Path
import os
import shutil
from fastapi.staticfiles import StaticFiles

uploads_dir = Path(__file__).resolve().parent / "uploads"

# si uploads existe mais n'est pas un dossier, on le supprime
if uploads_dir.exists() and not uploads_dir.is_dir():
    uploads_dir.unlink()

# créer le dossier uploads
uploads_dir.mkdir(parents=True, exist_ok=True)

# monter le dossier
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


# ==============================
# PROFILE IMAGE UPLOAD (LOCAL)
# ==============================

@app.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    ext = file.filename.split(".")[-1]

    filename = f"{uuid.uuid4()}.{ext}"

    file_path = uploads_dir / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"/uploads/{filename}"

    current_user.profile_image = image_url
    db.commit()

    return {"image_url": image_url}


# ==============================
# ROOT
# ==============================

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")

import threading
import time


def billing_worker():
    while True:
        try:
            run_subscription_billing()
        except Exception as e:
            print("Subscription billing error:", e)

        time.sleep(3600)


threading.Thread(target=billing_worker, daemon=True).start()