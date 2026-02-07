from app.db import SessionLocal
from app.models import User

db = SessionLocal()
u = db.query(User).filter(User.email=="adminndk@haiti.com").first()
u.login_attempts = 0
u.blocked_until = None
u.status = "active"
db.commit()
db.close()
