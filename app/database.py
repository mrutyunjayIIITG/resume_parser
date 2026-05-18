from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - Your Supabase Connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
from sqlalchemy.dialects.postgresql import JSONB

class ResumeRecord(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    candidate_name = Column(String, index=True)
    email = Column(String, index=True)
    file_hash = Column(String, index=True)
    parsed_json = Column(JSONB)
    # Store as string for pgvector compatibility if not using pgvector-python
    embedding = Column(String) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SkillCategory(Base):
    __tablename__ = "skill_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class SkillMaster(Base):
    __tablename__ = "skills_master"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, index=True)
    canonical_name = Column(String, unique=True, index=True, nullable=False)

class SkillAlias(Base):
    __tablename__ = "skill_aliases"
    id = Column(Integer, primary_key=True)
    skill_id = Column(Integer, index=True)
    alias_name = Column(String, unique=True, index=True, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)

def check_existing_hash(file_hash):
    db = SessionLocal()
    try:
        return db.query(ResumeRecord).filter(ResumeRecord.file_hash == file_hash).first()
    finally:
        db.close()

def check_existing_email(email):
    if not email: return None
    db = SessionLocal()
    try:
        return db.query(ResumeRecord).filter(ResumeRecord.email == email).first()
    finally:
        db.close()

def save_resume(filename, parsed_data, embedding, file_hash):
    db = SessionLocal()
    try:
        # Convert list to string format [0.1, 0.2, ...] for pgvector
        vector_str = str(embedding) if embedding else None
        
        emails = parsed_data.get("contact", {}).get("emails", [])
        primary_email = emails[0] if emails else None
        
        record = ResumeRecord(
            filename=filename,
            candidate_name=parsed_data.get("candidate_name"),
            email=primary_email,
            file_hash=file_hash,
            parsed_json=parsed_data,
            embedding=vector_str
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id
    finally:
        db.close()

def get_all_resumes():
    db = SessionLocal()
    try:
        return db.query(ResumeRecord).all()
    finally:
        db.close()

def semantic_search_production(query_vector, threshold=0.5, limit=10):
    """
    Production-grade search using the match_resumes SQL function.
    Calculates similarity inside the database for maximum speed.
    """
    db = SessionLocal()
    try:
        # We call the stored procedure we created in Supabase
        result = db.execute(
            text("SELECT * FROM match_resumes(:vec, :thresh, :lim)"),
            {"vec": str(query_vector), "thresh": threshold, "lim": limit}
        )
        return [dict(row._mapping) for row in result]
    finally:
        db.close()
