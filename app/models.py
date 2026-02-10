from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import relationship
from datetime import datetime

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    status = Column(String, default="active")
# active | suspended | banned

    # identité
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    phone_verified = Column(Boolean, default=False)

    # parrainage
    ref_code = Column(String, unique=True, index=True)
    referred_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_qualified = Column(Boolean, default=False)
    ref_bonus_paid = Column(Boolean, default=False)
    referral_bonus_paid = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


    # relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    # relation vers le parrain (optionnel mais pratique)
    referrer = relationship("User", remote_side=[id], uselist=False)


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    htg = Column(Float, default=0.0, nullable=False)
    usd = Column(Float, default=0.0, nullable=False)

    user = relationship("User", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)       # topup | transfer | convert
    currency = Column(String, nullable=False)   # htg | usd
    amount = Column(Float, nullable=False)
    note = Column(String, default="", nullable=False)

    # IMPORTANT: SQLite chez toi l'a en NOT NULL -> on la garde NOT NULL
    direction = Column(String, nullable=False)  # credit | debit | htg_to_usd | usd_to_htg | transfer_in | transfer_out
    rate_used = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="transactions")


class TopupRequest(Base):
    __tablename__ = "topup_requests"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)
    fee_amount = Column(Float, default=0.0)   # ✅ AJOUT
    net_amount = Column(Float, default=0.0)   # ✅ AJOUT
    currency = Column(String, nullable=False)   # "htg" | "usd"
    method = Column(String, nullable=False)     # "moncash" | "natcash" | "interac"
    reference = Column(String, nullable=False)

    proof_url = Column(String, nullable=True)
    note = Column(String, nullable=True)

    status = Column(String, default="PENDING", nullable=False)  # PENDING/APPROVED/REJECTED
    admin_note = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)


class FxSetting(Base):
    __tablename__ = "fx_settings"

    id = Column(Integer, primary_key=True, index=True)
    sell_usd = Column(Float, default=134.0, nullable=False)
    buy_usd = Column(Float, default=126.0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# --- PARTNERS (où dépenser les crédits) ---
class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=False, default="autre")  # ex: food, shop, services
    url = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String(300), nullable=True)
    active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True, index=True)
    referrer_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    milestone = Column(Integer, nullable=False)  # 3
    amount_htg = Column(Float, nullable=False, default=500.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # (optionnel)
    note = Column(String, nullable=True)


class PhoneOTP(Base):
    __tablename__ = "phone_otps"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)

class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(Integer, primary_key=True)
    email = Column(String, index=True, nullable=False)
    token = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)