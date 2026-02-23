from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal, Dict
from datetime import datetime

# -------------------------
# AUTH
# -------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    ref: Optional[str] = None   # ✅ optionnel, ne bloque pas


class PhoneStartIn(BaseModel):
    phone: str


class PhoneVerifyIn(BaseModel):
    phone: str
    code: str
    email: EmailStr
    password: str
    ref: Optional[str] = None

    # ✅ NOUVEAU : identité légale
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)


class RegisterOut(BaseModel):
    ok: bool = True
    email: EmailStr
    role: str
    ref_code: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WalletOut(BaseModel):
    htg: float
    usd: float

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None


class RoleUpdateIn(BaseModel):
    role: str


class MeOut(BaseModel):
    email: str
    role: str
    ref_code: Optional[str] = None

    # ✅ NOUVEAU : infos user
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    phone_verified: Optional[bool] = None
    profile_picture: Optional[str] = None
    wallet: Dict[str, float]

    class Config:
        from_attributes = True


# ✅ NOUVEAU : Forgot / Reset password
class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ForgotPasswordOut(BaseModel):
    ok: bool = True
    message: str


class ResetPasswordIn(BaseModel):
    email: EmailStr
    token: str = Field(min_length=6, max_length=120)
    new_password: str = Field(min_length=6, max_length=120)


class ResetPasswordOut(BaseModel):
    ok: bool = True
    message: str

class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str

# -------------------------
# FX
# -------------------------
class FxIn(BaseModel):
    sell_usd: float
    buy_usd: float


class FxOut(BaseModel):
    sell_usd: float
    buy_usd: float

    class Config:
        from_attributes = True


# -------------------------
# WALLET - TRANSFER / CONVERT / TX LIST
# -------------------------
Currency = Literal["htg", "usd"]

class TransferIn(BaseModel):
    to_email: EmailStr
    currency: Currency
    amount: float = Field(gt=0)
    note: Optional[str] = ""


class ConvertIn(BaseModel):
    direction: Literal["htg_to_usd", "usd_to_htg"]
    amount: float = Field(gt=0)


class ConvertOut(BaseModel):
    from_currency: str
    to_currency: str
    amount_in: float
    amount_out: float
    rate_used: float
    direction: Optional[str] = None


class TxOut(BaseModel):
    id: int
    type: str
    currency: str
    amount: float
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


# -------------------------
# PROVIDER (mock MonCash / NatCash)
# -------------------------
class ProviderTopupIn(BaseModel):
    user_email: EmailStr
    provider: Literal["moncash", "natcash"]
    currency: Currency
    amount: float = Field(gt=0)


class ProviderTopupOut(BaseModel):
    ok: bool
    credited_amount: float
    currency: str
    note: str


# -------------------------
# TOPUP SAFE (REQUEST + ADMIN DECIDE)
# -------------------------
TopupMethod = Literal["moncash", "natcash", "interac"]
TopupStatus = Literal["PENDING", "APPROVED", "REJECTED"]

class TopupRequestIn(BaseModel):
    amount: float = Field(gt=0)
    currency: Currency
    method: TopupMethod
    reference: str = Field(min_length=3, max_length=120)
    proof_url: Optional[str] = None
    note: Optional[str] = None


class TopupRequestOut(BaseModel):
    id: int
    user_id: int
    user_email: EmailStr
    amount: float
    fee_amount: float
    net_amount: float
    currency: str
    method: str
    reference: str
    proof_url: Optional[str] = None
    note: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TopupDecisionIn(BaseModel):
    status: Literal["APPROVED", "REJECTED"]
    admin_note: Optional[str] = None


# -------------------------
# PARTNERS
# -------------------------
class PartnerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="autre", max_length=60)
    url: str = Field(min_length=5, max_length=300)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    active: bool = True


class PartnerOut(BaseModel):
    id: int
    name: str
    category: str
    url: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# -------------------------
# PARTNER SPEND
# -------------------------
class PartnerSpendIn(BaseModel):
    partner_id: int
    currency: Currency
    amount: float = Field(gt=0)
    note: Optional[str] = None


class PartnerSpendOut(BaseModel):
    ok: bool
    partner_id: int
    currency: str
    amount: float
    new_balance_htg: float
    new_balance_usd: float
    tx_id: int


class AdminAdjustIn(BaseModel):
    email: EmailStr
    currency: str  # "htg" | "usd"
    amount: float  # +credit / -debit
    note: Optional[str] = None


class AdminAdjustOut(BaseModel):
    ok: bool
    email: EmailStr
    currency: str
    amount: float
    new_balance_htg: float
    new_balance_usd: float
    tx_id: int
