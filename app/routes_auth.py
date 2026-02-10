from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
import string
import secrets

from .db import get_db
from .models import User, Wallet, PhoneOTP, PasswordReset
from .models_audit import AuditLog
from .schemas import (
    TokenOut, MeOut,
    PhoneStartIn, PhoneVerifyIn,
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
# OTP helpers
# -------------------------------------------------
def generate_otp_code(length=6):
    return "".join(secrets.choice(string.digits) for _ in range(length))


def normalize_phone(phone: str) -> str:
    return phone.strip()


def send_sms_simulated(phone: str, code: str):
    print(f"[SIMULATED SMS] to={phone} code={code}")


# -------------------------------------------------
# PHONE OTP START
# -------------------------------------------------
@router.post("/phone/start")
def phone_start(data: PhoneStartIn, db: Session = Depends(get_db)):
    phone = normalize_phone(data.phone)
    if len(phone) < 8:
        raise HTTPException(400, "Numéro invalide")

    last = (
        db.query(PhoneOTP)
        .filter(PhoneOTP.phone == phone)
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )
    if last and (datetime.utcnow() - last.created_at).total_seconds() < 60:
        raise HTTPException(429, "Attends 60 secondes avant de redemander un code")

    code = generate_otp_code()
    now = datetime.utcnow()

    otp = PhoneOTP(
        phone=phone,
        code=code,
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        used=False,
    )
    db.add(otp)
    db.commit()

    send_sms_simulated(phone, code)
    return {"ok": True, "message": "Code envoyé (valide 10 minutes)"}


# -------------------------------------------------
# VERIFY OTP + REGISTER
# -------------------------------------------------
@router.post("/phone/verify_register", response_model=TokenOut)
def phone_verify_and_register(data: PhoneVerifyIn, db: Session = Depends(get_db)):
    phone = normalize_phone(data.phone)
    email = data.email.lower().strip()
    password = data.password.strip()

    if len(password) < 6:
        raise HTTPException(400, "Mot de passe trop court")

    otp = (
        db.query(PhoneOTP)
        .filter(
            PhoneOTP.phone == phone,
            PhoneOTP.code == data.code,
            PhoneOTP.used == False,
        )
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400, "Code invalide ou expiré")

    otp.used = True
    db.commit()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Email déjà utilisé")
    
    existing_user = db.query(User).filter(User.phone == phone).first()
    if existing_user:
        raise HTTPException(
        status_code=400,
        detail="Ce numéro est déjà utilisé."
    )


    user = User(
        email=email,
        phone=phone,
        phone_verified=True,
        password_hash=hash_password(password),
        role="user",
        ref_code=generate_ref_code(db),
        created_at=datetime.utcnow(),
        first_name=data.first_name,
        last_name=data.last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    wallet = Wallet(user_id=user.id, htg=0.0, usd=0.0)
    db.add(wallet)
    db.commit()

    token = create_access_token(subject=user.email)
    return TokenOut(access_token=token)


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
        wallet={
            "htg": float(user.wallet.htg) if user.wallet else 0.0,
            "usd": float(user.wallet.usd) if user.wallet else 0.0,
        },
    )
