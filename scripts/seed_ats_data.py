import os
import sys

# Add the parent directory to sys.path so we can import 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.database import (
    SessionLocal, init_db,
    LocationMaster, LocationAlias,
    DesignationMaster, DesignationAlias,
    CompanyMaster, CompanyAlias,
    DegreeMaster, DegreeAlias
)

def seed_ats_data():
    print("Starting init_db()...")
    init_db()
    print("init_db() finished. Creating session...")
    db = SessionLocal()
    print("Session created. Beginning seed...")
    try:
        # Seed Locations
        locations = {
            "Bangalore": ["bengaluru", "blr"],
            "New York": ["nyc", "new york city"],
            "San Francisco": ["sf", "san francisco bay area"],
            "Hyderabad": ["hyd"]
        }
        for canon, aliases in locations.items():
            loc = db.query(LocationMaster).filter_by(canonical_location=canon).first()
            if not loc:
                loc = LocationMaster(canonical_location=canon, country="Unknown", state="Unknown")
                db.add(loc)
                db.flush()
            for alias in aliases:
                if not db.query(LocationAlias).filter_by(alias=alias).first():
                    db.add(LocationAlias(alias=alias, location_id=loc.id))
        
        # Seed Designations
        designations = {
            "Software Engineer": ["sde", "software developer", "se", "programmer"],
            "Senior Software Engineer": ["sr dev", "senior developer", "sse", "senior software developer"],
            "Engineering Manager": ["em", "manager engineering"],
            "Data Scientist": ["ds", "data analyst"]
        }
        for canon, aliases in designations.items():
            desg = db.query(DesignationMaster).filter_by(canonical_designation=canon).first()
            if not desg:
                desg = DesignationMaster(canonical_designation=canon, seniority_level="Mid")
                db.add(desg)
                db.flush()
            for alias in aliases:
                if not db.query(DesignationAlias).filter_by(alias=alias).first():
                    db.add(DesignationAlias(alias=alias, designation_id=desg.id))
        
        # Seed Companies
        companies = {
            "Tata Consultancy Services": ["tcs"],
            "Infosys": ["infy"],
            "Wipro": ["wipro technologies"],
            "Cognizant": ["cts", "cognizant technology solutions"]
        }
        for canon, aliases in companies.items():
            comp = db.query(CompanyMaster).filter_by(canonical_company_name=canon).first()
            if not comp:
                comp = CompanyMaster(canonical_company_name=canon)
                db.add(comp)
                db.flush()
            for alias in aliases:
                if not db.query(CompanyAlias).filter_by(alias=alias).first():
                    db.add(CompanyAlias(alias=alias, company_id=comp.id))

        # Seed Degrees
        degrees = {
            "Bachelor of Technology": ["b.tech", "btech", "b tech", "bachelor of technology"],
            "Master of Technology": ["m.tech", "mtech", "m tech", "master of technology"],
            "Bachelor of Science": ["bsc", "b.sc", "b.s.", "bachelor of sci", "bachelor of science"],
            "Master of Business Administration": ["mba", "m.b.a", "master of business administration"]
        }
        for canon, aliases in degrees.items():
            deg = db.query(DegreeMaster).filter_by(canonical_degree=canon).first()
            if not deg:
                deg = DegreeMaster(canonical_degree=canon)
                db.add(deg)
                db.flush()
            for alias in aliases:
                if not db.query(DegreeAlias).filter_by(alias=alias).first():
                    db.add(DegreeAlias(alias=alias, degree_id=deg.id))
        
        db.commit()
        print("ATS Master Data seeded successfully!")
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_ats_data()
