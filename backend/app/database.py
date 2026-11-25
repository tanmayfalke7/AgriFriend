from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

class Base(DeclarativeBase): pass

class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default='indexed')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class QueryLog(Base):
    __tablename__ = 'query_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8))
    answer: Mapped[str] = mapped_column(Text)
    response_status: Mapped[str] = mapped_column(String(32))
    retrieval_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Feedback(Base):
    __tablename__ = 'feedback'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query_log_id: Mapped[int] = mapped_column(Integer)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

engine = None
SessionLocal = None
def init_db() -> bool:
    global engine, SessionLocal
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={'connect_timeout': 3})
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        return True
    except Exception:
        engine = None; SessionLocal = None
        return False
