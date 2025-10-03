import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

engine = create_engine(os.getenv("DATABASE_URL"), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
