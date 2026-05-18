from app.database import engine, ResumeRecord
from sqlalchemy import text
import os

def clear_database():
    print("Connecting to database...")
    with engine.connect() as connection:
        print("Clearing 'resumes' table...")
        connection.execute(text("TRUNCATE TABLE resumes RESTART IDENTITY CASCADE;"))
        connection.commit()
    print("Database cleared successfully! You can now start fresh.")

if __name__ == "__main__":
    clear_database()
