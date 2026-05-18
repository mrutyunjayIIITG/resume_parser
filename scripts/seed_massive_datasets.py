import os
import sys
import urllib.request
import csv
import io
import itertools

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.database import (
    SessionLocal,
    DesignationMaster, DesignationAlias,
    CompanyMaster, CompanyAlias,
    DegreeMaster, DegreeAlias
)

def seed_massive_datasets():
    print("Connecting to database...")
    db = SessionLocal()
    print("Database connected.")
    
    try:
        # --- 1. S&P 500 Companies ---
        print("Fetching S&P 500 companies dataset...")
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        csv_data = response.read().decode('utf-8')
        
        reader = csv.DictReader(io.StringIO(csv_data))
        companies_added = 0
        for row in reader:
            company_name = row['Security'].strip()
            symbol = row['Symbol'].strip()
            
            # Remove generic suffixes for aliases
            base_name = company_name.replace(" Inc.", "").replace(" Corp.", "").replace(" Company", "").strip()
            
            comp = db.query(CompanyMaster).filter_by(canonical_company_name=company_name).first()
            if not comp:
                comp = CompanyMaster(canonical_company_name=company_name)
                db.add(comp)
                db.flush()
                companies_added += 1
            
            aliases = list(set([base_name.lower(), symbol.lower()]))
            for alias in aliases:
                if len(alias) > 1 and not db.query(CompanyAlias).filter_by(alias=alias).first():
                    db.add(CompanyAlias(alias=alias, company_id=comp.id))
            
            if companies_added % 100 == 0:
                db.commit()
                
        db.commit()
        print(f"Seeded {companies_added} new S&P 500 companies.")

        # --- 2. Procedural Job Titles ---
        print("Generating Procedural IT Job Titles...")
        seniorities = ["", "Junior", "Senior", "Lead", "Principal", "Chief", "Staff"]
        techs = ["Software", "Frontend", "Backend", "Full Stack", "Data", "Machine Learning", "DevOps", "Cloud", "QA", "Systems", "Security", "AI", "Mobile", "iOS", "Android", "Platform"]
        roles = ["Engineer", "Developer", "Architect", "Analyst", "Scientist", "Administrator", "Manager"]
        
        combinations = list(itertools.product(seniorities, techs, roles))
        
        designations_added = 0
        for s, t, r in combinations:
            # e.g., "Senior Software Engineer"
            title = f"{s} {t} {r}".strip()
            # Avoid weird combinations
            if "QA Scientist" in title or "Frontend Administrator" in title:
                continue
                
            desg = db.query(DesignationMaster).filter_by(canonical_designation=title).first()
            if not desg:
                sen_level = s if s else "Mid"
                desg = DesignationMaster(canonical_designation=title, seniority_level=sen_level)
                db.add(desg)
                db.flush()
                designations_added += 1
            
            # Generate acronym alias, e.g. "Senior Software Engineer" -> "sse"
            acronym = "".join([word[0] for word in title.split()]).lower()
            if len(acronym) >= 2 and not db.query(DesignationAlias).filter_by(alias=acronym).first():
                db.add(DesignationAlias(alias=acronym, designation_id=desg.id))
                
            if designations_added % 200 == 0:
                db.commit()
                
        db.commit()
        print(f"Seeded {designations_added} generated Job Titles.")

        # --- 3. Procedural Degrees ---
        print("Generating Procedural Degrees...")
        levels = ["Bachelor of", "Master of", "Doctor of Philosophy in", "Associate of"]
        fields = ["Science", "Arts", "Engineering", "Technology", "Computer Applications", "Business Administration", "Commerce", "Information Technology", "Data Science"]
        
        deg_added = 0
        for l, f in itertools.product(levels, fields):
            degree = f"{l} {f}".strip()
            
            deg_obj = db.query(DegreeMaster).filter_by(canonical_degree=degree).first()
            if not deg_obj:
                deg_obj = DegreeMaster(canonical_degree=degree)
                db.add(deg_obj)
                db.flush()
                deg_added += 1
                
            if l == "Bachelor of":
                prefix = "b"
            elif l == "Master of":
                prefix = "m"
            elif l == "Doctor of Philosophy in":
                prefix = "phd"
            else:
                prefix = "a"
                
            field_acronym = "".join([word[0] for word in f.split()]).lower()
            
            alias_list = []
            if prefix in ["b", "m"]:
                alias_list = [f"{prefix}.{field_acronym}", f"{prefix}{field_acronym}", f"{prefix} {field_acronym}"]
                if f == "Technology":
                    alias_list.extend([f"{prefix}.tech", f"{prefix}tech"])
                if f == "Science":
                    alias_list.extend([f"{prefix}.sc", f"{prefix}sc"])
            
            for alias in alias_list:
                if len(alias) >= 2 and not db.query(DegreeAlias).filter_by(alias=alias).first():
                    db.add(DegreeAlias(alias=alias, degree_id=deg_obj.id))
                    
            if deg_added % 100 == 0:
                db.commit()
                
        db.commit()
        print(f"Seeded {deg_added} generated Degrees.")
        print("Massive dataset seeding complete!")
        
    except Exception as e:
        db.rollback()
        print(f"Failed to seed data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_massive_datasets()
