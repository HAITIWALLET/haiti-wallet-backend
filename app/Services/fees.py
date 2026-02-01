# app/Services/fees.py

def compute_fee(amount: float) -> float:
    a = float(amount or 0)
    if a <= 0:
        return 0.0
    if a <= 20:
        return 1.5
    if a <= 50:
        return 3.0
    if a <= 70:
        return 5.0
    return 7.5

def net_amount(amount: float) -> float:
    a = float(amount or 0)
    f = compute_fee(a)
    n = a - f
    return n if n > 0 else 0.0
