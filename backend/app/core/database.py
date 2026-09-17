import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def run_db_migrations():
    """Safely adds missing columns to existing tables without data loss."""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "messages" in tables:
            columns = [c["name"] for c in inspector.get_columns("messages")]
            with engine.connect() as conn:
                if "status" not in columns:
                    logger.info("Migrating messages table: adding status column")
                    conn.execute(text("ALTER TABLE messages ADD COLUMN status VARCHAR(20) DEFAULT 'completed'"))
                if "model" not in columns:
                    logger.info("Migrating messages table: adding model column")
                    conn.execute(text("ALTER TABLE messages ADD COLUMN model VARCHAR(100)"))
                if "updated_at" not in columns:
                    logger.info("Migrating messages table: adding updated_at column")
                    conn.execute(text("ALTER TABLE messages ADD COLUMN updated_at DATETIME"))
                conn.commit()
    except Exception as e:
        logger.warning(f"Database migration check notice: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
