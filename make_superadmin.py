from app.db import SessionLocal
from app.models import User

db = SessionLocal()
u = db.query(User).filter(User.email == "admin@haiti.com").first()
if not u:
    print("User not found")
else:
    u.role = "superadmin"
    db.commit()
    print("OK ->", u.email, u.role)
db.close()
