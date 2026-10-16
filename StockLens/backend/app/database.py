"""Database engine/session configuration; not imported by frontend code."""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DATA_DIRECTORY = ROOT / 'data'
DATA_DIRECTORY.mkdir(exist_ok=True)

DATABASE_URL = os.getenv('DATABASE_URL', '').strip() or f'sqlite:///{DATA_DIRECTORY / "stocklens.sqlite3"}'
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = 'postgresql://' + DATABASE_URL[len('postgres://'):]
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = 'postgresql+psycopg2://' + DATABASE_URL[len('postgresql://'):]

is_sqlite = DATABASE_URL.startswith('sqlite:')
connect_args = {'check_same_thread': False, 'timeout': 30} if is_sqlite else ({} if 'sslmode=' in DATABASE_URL else {'sslmode':'require'})
engine_kwargs = {'pool_pre_ping': True}
if not is_sqlite and ':6543/' in DATABASE_URL:
    engine_kwargs['poolclass'] = NullPool  # transaction-pooler compatible
engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
