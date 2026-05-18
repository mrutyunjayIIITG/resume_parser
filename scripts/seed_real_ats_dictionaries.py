import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.database import (
    SessionLocal,
    DesignationMaster, DesignationAlias,
    CompanyMaster, CompanyAlias,
    DegreeMaster, DegreeAlias
)

def seed_real_dictionaries():
    print("Connecting to database...")
    db = SessionLocal()
    print("Database connected. Starting dictionary seed...")
    
    try:
        # 1. SEED DEGREES (Comprehensive List)
        degrees = {
            "Bachelor of Technology": ["b.tech", "btech", "b tech", "bachelor of engineering", "b.e", "b.e."],
            "Master of Technology": ["m.tech", "mtech", "m tech", "master of engineering", "m.e", "m.e."],
            "Bachelor of Science": ["bsc", "b.sc", "b.s.", "bs", "bachelor of sci"],
            "Master of Science": ["msc", "m.sc", "m.s.", "ms", "master of sci"],
            "Bachelor of Computer Applications": ["bca", "b.c.a"],
            "Master of Computer Applications": ["mca", "m.c.a"],
            "Bachelor of Arts": ["ba", "b.a", "b.a."],
            "Master of Arts": ["ma", "m.a", "m.a."],
            "Bachelor of Commerce": ["bcom", "b.com"],
            "Master of Commerce": ["mcom", "m.com"],
            "Master of Business Administration": ["mba", "m.b.a", "pgdm"],
            "Doctor of Philosophy": ["phd", "ph.d", "doctorate"],
            "Diploma": ["polytechnic diploma", "pg diploma"],
            "High School": ["10th", "12th", "ssc", "hsc", "cbse", "icse", "matriculation", "intermediate"]
        }
        
        print(f"Seeding {len(degrees)} core Degrees...")
        for canon, aliases in degrees.items():
            deg = db.query(DegreeMaster).filter_by(canonical_degree=canon).first()
            if not deg:
                deg = DegreeMaster(canonical_degree=canon)
                db.add(deg)
                db.flush()
            for alias in aliases:
                if not db.query(DegreeAlias).filter_by(alias=alias).first():
                    db.add(DegreeAlias(alias=alias, degree_id=deg.id))
                    
        # 2. SEED JOB TITLES (Top 50+ Tech Roles)
        designations = {
            "Software Engineer": ["sde", "software developer", "se", "programmer", "application developer"],
            "Senior Software Engineer": ["sr dev", "senior developer", "sse", "sde 2", "sde ii", "senior software developer", "senior sde"],
            "Lead Engineer": ["tech lead", "technical lead", "lead software engineer", "lead developer"],
            "Engineering Manager": ["em", "manager engineering", "software engineering manager", "sdm", "software development manager"],
            "Frontend Developer": ["ui developer", "front end engineer", "frontend engineer", "react developer", "angular developer"],
            "Backend Developer": ["backend engineer", "back end developer", "java developer", "python developer", "node developer"],
            "Full Stack Developer": ["fullstack engineer", "full stack engineer", "fullstack developer", "mern stack developer", "mean stack developer"],
            "Data Scientist": ["ds", "data science engineer", "machine learning scientist"],
            "Data Engineer": ["de", "big data engineer", "data pipeline engineer"],
            "Machine Learning Engineer": ["ml engineer", "mle", "ai engineer", "artificial intelligence engineer"],
            "DevOps Engineer": ["devops", "cloud engineer", "platform engineer", "build engineer"],
            "Site Reliability Engineer": ["sre", "reliability engineer"],
            "Quality Assurance Engineer": ["qa engineer", "qa", "software tester", "manual tester", "test engineer"],
            "Software Development Engineer in Test": ["sdet", "automation tester", "automation engineer", "qa automation"],
            "Product Manager": ["pm", "technical product manager", "tpm"],
            "Project Manager": ["project lead", "it project manager", "scrum master", "agile coach"],
            "UI/UX Designer": ["ux designer", "ui designer", "product designer", "interaction designer"],
            "Systems Analyst": ["system analyst", "it analyst"],
            "Business Analyst": ["ba", "technical business analyst"],
            "Database Administrator": ["dba", "database engineer", "sql developer"],
            "Chief Technology Officer": ["cto", "vp of engineering", "head of engineering", "director of engineering"]
        }
        
        print(f"Seeding {len(designations)} core Job Titles...")
        for canon, aliases in designations.items():
            desg = db.query(DesignationMaster).filter_by(canonical_designation=canon).first()
            if not desg:
                desg = DesignationMaster(canonical_designation=canon, seniority_level="Mixed")
                db.add(desg)
                db.flush()
            for alias in aliases:
                if not db.query(DesignationAlias).filter_by(alias=alias).first():
                    db.add(DesignationAlias(alias=alias, designation_id=desg.id))

        # 3. SEED COMPANIES (Top Global & Indian Tech/MNCs)
        companies = {
            "Tata Consultancy Services": ["tcs", "tata consultancy"],
            "Infosys": ["infy", "infosys limited", "infosys ltd"],
            "Wipro": ["wipro technologies", "wipro limited"],
            "Cognizant": ["cts", "cognizant technology solutions"],
            "HCL Technologies": ["hcl", "hcltech"],
            "Tech Mahindra": ["techm", "tech mahindra limited"],
            "Accenture": ["accenture solutions", "accenture india"],
            "Capgemini": ["capgemini india"],
            "IBM": ["ibm india", "international business machines"],
            "Microsoft": ["microsoft india", "microsoft corporation"],
            "Google": ["google india", "alphabet"],
            "Amazon": ["amazon development centre", "aws", "amazon web services"],
            "Meta": ["facebook", "meta platforms"],
            "Apple": ["apple inc", "apple india"],
            "Oracle": ["oracle india", "oracle corporation"],
            "SAP": ["sap labs", "sap india"],
            "Salesforce": ["salesforce india"],
            "Cisco": ["cisco systems"],
            "Intel": ["intel corporation"],
            "NVIDIA": ["nvidia graphics"],
            "AMD": ["advanced micro devices"],
            "VMware": ["vmware software"],
            "Adobe": ["adobe systems"],
            "Intuit": ["intuit india"],
            "Flipkart": ["flipkart internet"],
            "Amazon": ["amazon.com"],
            "Swiggy": ["bundl technologies"],
            "Zomato": ["zomato media"],
            "Uber": ["uber india"],
            "Paytm": ["one97 communications"],
            "Ola": ["ani technologies", "ola cabs"],
            "Deloitte": ["deloitte consulting", "deloitte touche tohmatsu"],
            "PwC": ["pricewaterhousecoopers", "pwc india"],
            "EY": ["ernst & young", "ey india"],
            "KPMG": ["kpmg india"],
            "JP Morgan Chase": ["jp morgan", "jpmc"],
            "Goldman Sachs": ["goldman sachs india"],
            "Morgan Stanley": ["morgan stanley advantage services"],
            "Wells Fargo": ["wells fargo india"]
        }
        
        print(f"Seeding {len(companies)} top IT/MNC Companies...")
        for canon, aliases in companies.items():
            comp = db.query(CompanyMaster).filter_by(canonical_company_name=canon).first()
            if not comp:
                comp = CompanyMaster(canonical_company_name=canon)
                db.add(comp)
                db.flush()
            for alias in aliases:
                if not db.query(CompanyAlias).filter_by(alias=alias).first():
                    db.add(CompanyAlias(alias=alias, company_id=comp.id))

        db.commit()
        print("Real Dictionary ATS Data successfully seeded!")
        
    except Exception as e:
        db.rollback()
        print(f"Failed to seed real dictionary data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_real_dictionaries()
