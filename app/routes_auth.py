from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
import string
import secrets
import time
from .db import get_db
from .models import User, Wallet, PasswordReset
from .models_audit import AuditLog
from .schemas import (
    TokenOut, MeOut,
    RegisterIn,
    ForgotPasswordIn, ForgotPasswordOut,
    ResetPasswordIn, ResetPasswordOut,
    ChangePasswordSchema
)
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# -------------------------------------------------
# Password validation
# -------------------------------------------------
def validate_password(pwd: str):
    if len(pwd) < 8:
        raise HTTPException(400, "Mot de passe trop court")
    if not any(c.isdigit() for c in pwd):
        raise HTTPException(400, "Mot de passe doit contenir un chiffre")
    if not any(c.isalpha() for c in pwd):
        raise HTTPException(400, "Mot de passe doit contenir une lettre")


# -------------------------------------------------
# Parrainage
# -------------------------------------------------
def generate_ref_code(db: Session, length=8):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            exists = db.query(User).filter(User.ref_code == code).first()
        except OperationalError:
            return code
        if not exists:
            return code

# -------------------------------------------------
# REGISTER
# -------------------------------------------------
@router.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):

    email = data.email.lower().strip()
    password = data.password.strip()
    first_name = data.first_name
    last_name = data.last_name
    ref = data.ref

    validate_password(password)

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "Email déjà utilisé")

    my_ref_code = generate_ref_code(db)

    referred_by_user_id = None
    if ref:
        ref_user = db.query(User).filter(User.ref_code == ref).first()
        if ref_user:
            referred_by_user_id = ref_user.id

    user = User(
        email=email,
        password_hash=hash_password(password),
        role="user",
        status="active",
        first_name=first_name,
        last_name=last_name,
        ref_code=my_ref_code,
        referred_by_user_id=referred_by_user_id
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    wallet = Wallet(user_id=user.id)
    db.add(wallet)
    db.commit()

    return {
        "ok": True,
        "email": user.email,
        "role": user.role,
        "ref_code": user.ref_code
    }

# -------------------------------------------------
# PASSWORD FORGOT / RESET
# -------------------------------------------------
@router.post("/password/forgot", response_model=ForgotPasswordOut)
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    token = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    now = datetime.utcnow()

    if user:
        pr = PasswordReset(
            email=email,
            token=token,
            created_at=now,
            expires_at=now + timedelta(minutes=15),
            used=False,
        )
        db.add(pr)
        db.commit()
        print(f"[RESET PASSWORD] email={email} token={token}")

    return ForgotPasswordOut(ok=True, message="Si l'email existe, un code a été envoyé")


@router.post("/password/reset", response_model=ResetPasswordOut)
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    pr = (
        db.query(PasswordReset)
        .filter(
            PasswordReset.email == data.email.lower(),
            PasswordReset.token == data.token.upper(),
            PasswordReset.used == False,
        )
        .order_by(PasswordReset.created_at.desc())
        .first()
    )
    if not pr or pr.expires_at < datetime.utcnow():
        raise HTTPException(400, "Code invalide ou expiré")

    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        raise HTTPException(400, "Utilisateur introuvable")

    user.password_hash = hash_password(data.new_password)
    pr.used = True
    db.commit()

    return ResetPasswordOut(ok=True, message="Mot de passe mis à jour")


@router.post("/password/change")
def change_password(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(400, "Ancien mot de passe incorrect")

    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True, "message": "Password updated successfully"}


# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):

    email = form.username.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()

    if not user or not verify_password(form.password, user.password_hash):
        time.sleep(1)
        raise HTTPException(401, "Email ou mot de passe incorrect")

    if user.status != "active":
        raise HTTPException(403, "Compte suspendu ou banni")

    token = create_access_token(subject=user.email)

    db.add(AuditLog(
        user_id=user.id,
        action="login_success",
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    return TokenOut(access_token=token)


# -------------------------------------------------
# ME
# -------------------------------------------------
@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(
        email=user.email,
        role=user.role,
        ref_code=user.ref_code,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        phone_verified=user.phone_verified,
        profile_image=user.profile_image,
        wallet={
            "htg": float(user.wallet.htg) if user.wallet else 0.0,
            "usd": float(user.wallet.usd) if user.wallet else 0.0,
        },
    )

from fastapi import Depends
from sqlalchemy.orm import Session
from app.db import get_db   # adapte si chemin différent

@router.put("/me")
def update_me(
    data: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user.first_name = data.get("first_name", user.first_name)
    user.last_name = data.get("last_name", user.last_name)
    user.phone = data.get("phone", user.phone)

    db.commit()
    db.refresh(user)

    return {"success": True}

from fastapi import UploadFile, File
import shutil
from uuid import uuid4
import os


import smtplib
from email.mime.text import MIMEText

def send_email(to_email, content):
    import os
    import smtplib
    from email.mime.text import MIMEText

    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    msg = MIMEText(content)
    msg["Subject"] = "Haiti Wallet Notification"
    msg["From"] = smtp_user
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

from pydantic import BaseModel

class DeleteAccountRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    reason: str


@router.post("/request-delete-account")
def request_delete_account(data: DeleteAccountRequest):

    subject = "Demande de suppression de compte - Haiti Wallet"

    body = f"""
    Nouvelle demande de suppression :

    Nom: {data.first_name}
    Prénom: {data.last_name}
    Email: {data.email}

    Raison:
    {data.reason}
    """

    send_email("contacthaitiwallet@gmail.com", body)

    return {"message": "Request sent successfully"}