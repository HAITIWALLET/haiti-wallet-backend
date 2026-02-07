from app.db import SessionLocal
from app.models import User

db = SessionLocal()

user = db.query(User).filter(User.email == "admin@haiti.com").first()

if not user:
    print("Utilisateur introuvable")
else:
    user.status = "active"
    db.commit()
    print("Utilisateur débloqué")

db.close()
