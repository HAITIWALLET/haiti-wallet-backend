def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
