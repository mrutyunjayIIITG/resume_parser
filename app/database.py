from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, text, ForeignKey, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

# Load .env from the root directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

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
    raw_text = Column(String)
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

# --- CEIPAL-Style Master Normalization Tables ---

class LocationMaster(Base):
    __tablename__ = "locations_master"
    id = Column(Integer, primary_key=True)
    canonical_location = Column(String, unique=True, index=True, nullable=False)
    country = Column(String)
    state = Column(String)

class LocationAlias(Base):
    __tablename__ = "location_aliases"
    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    location_id = Column(Integer, ForeignKey("locations_master.id"), index=True)

class DesignationMaster(Base):
    __tablename__ = "designations_master"
    id = Column(Integer, primary_key=True)
    canonical_designation = Column(String, unique=True, index=True, nullable=False)
    seniority_level = Column(String)

class DesignationAlias(Base):
    __tablename__ = "designation_aliases"
    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    designation_id = Column(Integer, ForeignKey("designations_master.id"), index=True)

class CompanyMaster(Base):
    __tablename__ = "companies_master"
    id = Column(Integer, primary_key=True)
    canonical_company_name = Column(String, unique=True, index=True, nullable=False)

class CompanyAlias(Base):
    __tablename__ = "company_aliases"
    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies_master.id"), index=True)

class DegreeMaster(Base):
    __tablename__ = "degrees_master"
    id = Column(Integer, primary_key=True)
    canonical_degree = Column(String, unique=True, index=True, nullable=False)

class DegreeAlias(Base):
    __tablename__ = "degree_aliases"
    id = Column(Integer, primary_key=True)
    alias = Column(String, unique=True, index=True, nullable=False)
    degree_id = Column(Integer, ForeignKey("degrees_master.id"), index=True)

# --- CEIPAL-Style Candidate Storage Tables ---

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, index=True)
    email = Column(String, index=True)
    phone = Column(String, index=True)
    current_location_id = Column(Integer, ForeignKey("locations_master.id"), index=True, nullable=True)
    raw_current_location = Column(String)
    total_experience_years = Column(Integer)
    current_designation_id = Column(Integer, ForeignKey("designations_master.id"), index=True, nullable=True)
    raw_current_designation = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    source = Column(String, default="Direct Upload")
    # Keeping reference to the original raw parse if needed
    resume_record_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)

class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    skill_id = Column(Integer, ForeignKey("skills_master.id"), index=True)
    years_of_experience = Column(Integer, nullable=True)

class CandidateExperience(Base):
    __tablename__ = "candidate_experience"
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    company_id = Column(Integer, ForeignKey("companies_master.id"), index=True, nullable=True)
    raw_company_name = Column(String)
    designation_id = Column(Integer, ForeignKey("designations_master.id"), index=True, nullable=True)
    raw_designation = Column(String)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    currently_working = Column(Boolean, default=False)

class CandidateEducation(Base):
    __tablename__ = "candidate_education"
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), index=True)
    degree_id = Column(Integer, ForeignKey("degrees_master.id"), index=True, nullable=True)
    raw_degree = Column(String)
    institution_name = Column(String)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)

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

def save_resume(filename, parsed_data, embedding, file_hash, raw_text=None, source="Direct Upload"):
    db = SessionLocal()
    try:
        # Convert list to string format [0.1, 0.2, ...] for pgvector
        vector_str = str(embedding) if embedding else None
        
        contact = parsed_data.get("contact", {}) if isinstance(parsed_data, dict) else {}
        emails = []
        if isinstance(contact, dict):
            emails = contact.get("emails", [])
        elif isinstance(contact, list):
            emails = [item for item in contact if isinstance(item, str) and "@" in item]
            
        if not isinstance(emails, list):
            emails = [emails] if isinstance(emails, str) else []
            
        primary_email = emails[0] if emails else None
        
        record = ResumeRecord(
            filename=filename,
            candidate_name=parsed_data.get("candidate_name"),
            email=primary_email,
            file_hash=file_hash,
            parsed_json=parsed_data,
            embedding=vector_str,
            raw_text=raw_text
        )
        db.add(record)
        db.flush()
        
        # --- ATS Normalized Storage ---
        ats_data = parsed_data.get("ats_normalized", {})
        phones = contact.get("phones", []) if isinstance(contact, dict) else []
        phone = phones[0] if phones else None
        
        candidate = Candidate(
            full_name=parsed_data.get("candidate_name"),
            email=primary_email,
            phone=phone,
            current_location_id=ats_data.get("location", {}).get("id"),
            raw_current_location=ats_data.get("location", {}).get("raw"),
            resume_record_id=record.id,
            source=source
        )
        
        designations = ats_data.get("designations", [])
        if designations:
            candidate.current_designation_id = designations[0].get("id")
            candidate.raw_current_designation = designations[0].get("raw")
            
        db.add(candidate)
        db.flush()
        
        # Save Skills mapping
        skills_found = parsed_data.get("skills", [])
        if skills_found:
            skill_masters = db.query(SkillMaster).filter(SkillMaster.canonical_name.in_(skills_found)).all()
            
            # Map years of experience if available
            skills_detailed = parsed_data.get("skills_detailed", [])
            skill_years_map = {s.get("name", "").lower(): s.get("years_of_experience") for s in skills_detailed if isinstance(s, dict)}
            
            for sm in skill_masters:
                yoe = skill_years_map.get(sm.canonical_name.lower())
                db.add(CandidateSkill(candidate_id=candidate.id, skill_id=sm.id, years_of_experience=yoe))
                
        # Save Experience
        # Using Gemini's detailed experience extraction if available
        exp_detailed = parsed_data.get("experience_detailed", [])
        if exp_detailed and isinstance(exp_detailed, list):
            for exp in exp_detailed:
                if not isinstance(exp, dict): continue
                # Find matching company and designation from the normalized lists
                c_name = exp.get("company", "")
                r_name = exp.get("role", "")
                
                # Match to normalized lists
                comp_id = next((c.get("id") for c in ats_data.get("companies", []) if c.get("raw") == c_name), None)
                desig_id = next((d.get("id") for d in designations if d.get("raw") == r_name), None)
                
                import datetime
                def parse_date(date_str):
                    if not date_str: return None
                    try: return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    except: return None
                
                db.add(CandidateExperience(
                    candidate_id=candidate.id,
                    company_id=comp_id,
                    raw_company_name=c_name,
                    designation_id=desig_id,
                    raw_designation=r_name,
                    start_date=parse_date(exp.get("start_date")),
                    end_date=parse_date(exp.get("end_date")),
                    currently_working=exp.get("is_current", False)
                ))
        else:
            # Fallback to flattened logic if detailed not available
            for desig in designations:
                db.add(CandidateExperience(
                    candidate_id=candidate.id,
                    designation_id=desig.get("id"),
                    raw_designation=desig.get("raw")
                ))
            for comp in ats_data.get("companies", []):
                db.add(CandidateExperience(
                    candidate_id=candidate.id,
                    company_id=comp.get("id"),
                    raw_company_name=comp.get("raw")
                ))
            
        # Save Education
        for deg in ats_data.get("degrees", []):
            db.add(CandidateEducation(
                candidate_id=candidate.id,
                degree_id=deg.get("id"),
                raw_degree=deg.get("raw")
            ))

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

def get_skills_with_aliases():
    """Fetches all skills grouped with their aliases and category."""
    db = SessionLocal()
    try:
        # Import models inside function to avoid circular dependencies
        from app.database import SkillCategory, SkillMaster, SkillAlias
        
        categories = {c.id: c.name for c in db.query(SkillCategory).all()}
        masters = db.query(SkillMaster).all()
        aliases = db.query(SkillAlias).all()
        
        # Group aliases by skill_id
        skill_aliases = {}
        for alias in aliases:
            skill_aliases.setdefault(alias.skill_id, []).append(alias.alias_name)
            
        result = []
        for master in masters:
            cat_name = categories.get(master.category_id, "Tech Skill")
            result.append({
                "id": master.id,
                "canonical_name": master.canonical_name,
                "category": cat_name,
                "aliases": sorted(skill_aliases.get(master.id, []))
            })
            
        # Sort by category and canonical name
        return sorted(result, key=lambda x: (x["category"], x["canonical_name"]))
    finally:
        db.close()
