import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SQLITE_URL = os.environ.get("SQLITE_URL", "sqlite:///../data/lead_generation.db")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_size=50, max_overflow=25, pool_pre_ping=True, pool_recycle=3600)
else:
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
