import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    with engine.connect() as conn:
        try:
            print("Adding raw_text to resumes...")
            conn.execute(text("ALTER TABLE resumes ADD COLUMN raw_text TEXT;"))
            conn.commit()
            print("Success!")
        except Exception as e:
            print(f"Skipped (already exists or error): {e}")
            conn.rollback()

        try:
            print("Adding source to candidates...")
            conn.execute(text("ALTER TABLE candidates ADD COLUMN source VARCHAR;"))
            conn.commit()
            print("Success!")
        except Exception as e:
            print(f"Skipped (already exists or error): {e}")
            conn.rollback()

        try:
            print("Adding years_of_experience to candidate_skills...")
            conn.execute(text("ALTER TABLE candidate_skills ADD COLUMN years_of_experience INTEGER;"))
            conn.commit()
            print("Success!")
        except Exception as e:
            print(f"Skipped (already exists or error): {e}")
            conn.rollback()

        try:
            print("Adding work_authorization to candidates...")
            conn.execute(text("ALTER TABLE candidates ADD COLUMN work_authorization VARCHAR;"))
            conn.commit()
            print("Success!")
        except Exception as e:
            print(f"Skipped (already exists or error): {e}")
            conn.rollback()

if __name__ == "__main__":
    run_migration()
    print("Migration complete!")
