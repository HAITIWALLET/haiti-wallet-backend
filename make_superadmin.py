# make_superadmin.py
import os
from dotenv import load_dotenv
from app.db import SessionLocal
from app.models import User
from app.security import hash_password

EMAIL = "adminndk@haiti.com"
PASSWORD = "@Haitiwallet20-26"  # choisis-le et GARDE-LE

db = SessionLocal()

user = db.query(User).filter(User.email == EMAIL).first()

if not user:
    print("❌ User not found")
else:
    user.role = "superadmin"
    user.password_hash = hash_password(PASSWORD)
    db.commit()
    print("✅ Superadmin prêt")
    print("Email:", EMAIL)
    print("Password:", PASSWORD)

db.close()
