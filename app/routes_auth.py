from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
import string
import secrets

from .db import get_db
from .models import User, Wallet, PhoneOTP, PasswordReset
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

# ============================
# LOGIN RATE LIMIT (SAFE)
# ============================

LOGIN_ATTEMPTS = {}  
MAX_ATTEMPTS = 5
BLOCK_MINUTES = 10

def check_login_rate_limit(key: str):
    now = datetime.utcnow()

    data = LOGIN_ATTEMPTS.get(key)

    if not data:
        LOGIN_ATTEMPTS[key] = {
            "count": 1,
            "blocked_until": None
        }
        return

    # si bloqué
    if data["blocked_until"] and now < data["blocked_until"]:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives. Réessaie plus tard."
        )

    data["count"] += 1

    if data["count"] >= MAX_ATTEMPTS:
        data["blocked_until"] = now + timedelta(minutes=BLOCK_MINUTES)
        data["count"] = 0
        raise HTTPException(
            status_code=429,
            detail="Compte temporairement bloqué."
        )

router = APIRouter(prefix="/auth", tags=["auth"])

def validate_password(pwd: str):
    if len(pwd) < 8:
        raise HTTPException(400, "Mot de passe trop court")
    if not any(c.isdigit() for c in pwd):
        raise HTTPException(400, "Mot de passe doit contenir un chiffre")
    if not any(c.isalpha() for c in pwd):
        raise HTTPException(400, "Mot de passe doit contenir une lettre")

# -------------------------------------------------
# Helper génération code parrainage UNIQUE
# -------------------------------------------------
def generate_ref_code(db: Session, length=8):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        # ⚠️ si DB pas migrée et ref_code absent, on évite de casser
        try:
            exists = db.query(User).filter(User.ref_code == code).first()
        except OperationalError:
            # fallback : retourne un code, mais tu devras migrer la DB
            return code
        if not exists:
            return code


# -------------------------------------------------
# Helpers OTP
# -------------------------------------------------
def generate_otp_code(length=6):
    return "".join(secrets.choice(string.digits) for _ in range(length))

def normalize_phone(phone: str) -> str:
    return phone.strip()

def send_sms_simulated(phone: str, code: str):
    # ✅ Mode test: on "simule" l'envoi SMS
    print(f"[SIMULATED SMS] to={phone} code={code}")


# -------------------------------------------------
# START PHONE OTP
# -------------------------------------------------
@router.post("/phone/start")
def phone_start(data: PhoneStartIn, db: Session = Depends(get_db)):
    phone = normalize_phone(data.phone)
    if len(phone) < 8:
        raise HTTPException(status_code=400, detail="Numéro invalide.")

    # Anti-spam simple: 1 OTP / 60s par numéro
    last = (
        db.query(PhoneOTP)
        .filter(PhoneOTP.phone == phone)
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )
    if last and (datetime.utcnow() - last.created_at).total_seconds() < 60:
        raise HTTPException(status_code=429, detail="Attends 60 secondes avant de redemander un code.")

    code = generate_otp_code(6)
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

    return {"ok": True, "message": "Code envoyé (valide 10 minutes)."}


# -------------------------------------------------
# VERIFY OTP + REGISTER
# -------------------------------------------------
@router.post("/phone/verify_register", response_model=TokenOut)
def phone_verify_and_register(data: PhoneVerifyIn, db: Session = Depends(get_db)):
    phone = normalize_phone(data.phone)
    code = data.code.strip()
    email = data.email.lower().strip()
    password = data.password.strip()
    ref_code_in = (data.ref or "").strip().upper() or None

    # ✅ nouveaux champs
    first_name = data.first_name.strip()
    last_name = data.last_name.strip()

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 6).")

    if len(first_name) < 2 or len(last_name) < 2:
        raise HTTPException(status_code=400, detail="Nom et prénom obligatoires.")

    # Vérifier OTP
    otp = (
        db.query(PhoneOTP)
        .filter(PhoneOTP.phone == phone, PhoneOTP.code == code, PhoneOTP.used == False)  # noqa: E712
        .order_by(PhoneOTP.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="Code invalide.")
    if otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Code expiré.")

    otp.used = True
    db.commit()

    # Vérifier email/phone uniques
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=400, detail="Numéro déjà utilisé")

    # Chercher parrain (OPTIONNEL)
    referrer = None
    if ref_code_in:
        # ⚠️ si ref_code n’existe pas dans DB, ça peut casser -> try/except
        try:
            referrer = db.query(User).filter(User.ref_code == ref_code_in).first()
        except OperationalError:
            referrer = None

    # Création user (✅ champs qui existent vraiment)
    user = User(
        email=email,
        phone=phone,
        phone_verified=True,
        password_hash=hash_password(password),
        role="user",
        ref_code=generate_ref_code(db),
        referred_by_user_id=referrer.id if referrer else None,
        referral_qualified=False,
        ref_bonus_paid=False,
        referral_bonus_paid=0,
        created_at=datetime.utcnow(),

        # ✅ nouveaux champs
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Wallet auto
    wallet = Wallet(user_id=user.id, htg=0.0, usd=0.0)
    db.add(wallet)
    db.commit()

    # Token direct après inscription
    token = create_access_token(subject=user.email)
    return TokenOut(access_token=token)


# -------------------------------------------------
# FORGOT PASSWORD (email) — DEV MODE (simulé)
# -------------------------------------------------
@router.post("/password/forgot", response_model=ForgotPasswordOut)
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # ✅ On ne révèle jamais si l'email existe ou pas (bonne pratique)
    token = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    now = datetime.utcnow()

    # si user existe, on enregistre un reset
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

        # ✅ mode dev: on imprime le code dans la console
        print(f"[RESET PASSWORD] email={email} token={token} (valide 15 min)")

    return ForgotPasswordOut(ok=True, message="Si cet email existe, un code de réinitialisation a été envoyé.")


@router.post("/password/reset", response_model=ResetPasswordOut)
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    email = data.email.lower().strip()
    token = data.token.strip().upper()
    new_password = data.new_password.strip()

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 6).")

    pr = (
        db.query(PasswordReset)
        .filter(PasswordReset.email == email, PasswordReset.token == token, PasswordReset.used == False)  # noqa: E712
        .order_by(PasswordReset.created_at.desc())
        .first()
    )
    if not pr:
        raise HTTPException(status_code=400, detail="Code invalide.")
    if pr.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Code expiré.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable.")

    user.password_hash = hash_password(new_password)
    pr.used = True
    db.commit()
    
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.utcnow()
    pr.used = True
    db.commit()


    return ResetPasswordOut(ok=True, message="Mot de passe mis à jour. Tu peux te connecter.")

@router.post("/password/change")
def change_password(
    data: ChangePasswordSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Old password incorrect")

    current_user.password_hash = hash_password(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.commit()

    return {"ok": True, "message": "Password updated successfully"}

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    key = f"{form.username}"
    check_login_rate_limit(key)

    if not verify_password(form.password, user.password_hash):
     check_login_rate_limit(key)
    raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    token = create_access_token(subject=user.email)
    return TokenOut(access_token=token)


# -------------------------------------------------
# ME
# -------------------------------------------------
@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    # ✅ user.wallet peut être None si wallet pas créé -> on sécurise
    htg = float(user.wallet.htg) if user.wallet else 0.0
    usd = float(user.wallet.usd) if user.wallet else 0.0

    return MeOut(
        email=user.email,
        role=user.role,
        ref_code=getattr(user, "ref_code", None),
        first_name=getattr(user, "first_name", None),
        last_name=getattr(user, "last_name", None),
        phone=getattr(user, "phone", None),
        phone_verified=getattr(user, "phone_verified", None),
        wallet={
            "htg": htg,
            "usd": usd,
        },
    )
