import urllib.request
import json
import gzip
import time
import logging
from app.database import SessionLocal, SkillCategory, SkillMaster, SkillAlias, init_db

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# List of StackOverflow tags that are generic concepts, not specific skills/tools
GENERIC_TAGS = {
    "arrays", "string", "regex", "performance", "list", "json", "xml", "math", 
    "for-loop", "if-statement", "variables", "function", "class", "object", 
    "algorithm", "loops", "multithreading", "image", "file", "date", "validation",
    "pdf", "video", "audio", "security", "testing", "api", "rest", "authentication",
    "authorization", "login", "windows", "macos", "linux", "ubuntu", "macos",
    "datetime", "time", "browser", "internet-explorer", "firefox", "safari",
    "google-chrome", "oop", "user-interface", "design-patterns", "architecture"
}

def fetch_stackoverflow_tags(pages=5, pagesize=100):
    """Fetches top tech tags from StackOverflow API."""
    tags = []
    logger.info(f"Fetching top {pages * pagesize} tags from StackOverflow...")
    for page in range(1, pages + 1):
        url = f"https://api.stackexchange.com/2.3/tags?page={page}&pagesize={pagesize}&order=desc&sort=popular&site=stackoverflow"
        try:
            req = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip'})
            resp = urllib.request.urlopen(req)
            data = json.loads(gzip.decompress(resp.read()))
            tags.extend([t['name'] for t in data.get('items', [])])
            time.sleep(0.5) # respect rate limit
        except Exception as e:
            logger.error(f"Failed to fetch SO tags on page {page}: {e}")
    return list(set(tags))

def process_tags(raw_tags):
    """Filters out generic tags and prepares them for the database."""
    processed = []
    for tag in raw_tags:
        if tag.lower() in GENERIC_TAGS or len(tag) <= 1:
            continue
        
        # Determine basic category
        cat = "Tech Skill"
        if tag.endswith(".js") or tag.endswith("js"):
            cat = "JavaScript Tech"
        elif tag in ["python", "java", "c#", "c++", "c", "php", "ruby", "go", "swift", "kotlin", "rust", "scala"]:
            cat = "Programming Language"
        elif "sql" in tag:
            cat = "Database"
            
        # Convert e.g., reactjs -> Reactjs, node.js -> Node.js
        canonical = tag.replace("-", " ").title()
        
        processed.append({
            "original_tag": tag,
            "canonical_name": canonical,
            "category": cat,
            "aliases": list(set([tag, tag.replace("-", ""), tag.replace("-", " "), tag.replace(".", "")]))
        })
    return processed

def seed_database_with_skills(processed_skills):
    """Inserts the processed skills into the Supabase database optimally."""
    init_db()
    db = SessionLocal()
    added_count = 0
    try:
        # 1. Load all existing data into memory dictionaries to minimize queries
        existing_cats = {c.name.lower(): c for c in db.query(SkillCategory).all()}
        existing_masters = {m.canonical_name.lower(): m for m in db.query(SkillMaster).all()}
        existing_aliases = {a.alias_name.lower() for a in db.query(SkillAlias).all()}
        
        for item in processed_skills:
            cat_name = item.get("category", "Tech Skill")
            canonical = item.get("canonical_name")
            aliases = item.get("aliases", [])
            
            if not canonical: continue

            # 2. Get or Create Category
            cat_key = cat_name.lower()
            if cat_key not in existing_cats:
                cat = SkillCategory(name=cat_name)
                db.add(cat)
                db.flush() # Need flush to get ID
                existing_cats[cat_key] = cat
            cat = existing_cats[cat_key]

            # 3. Get or Create Skill Master
            master_key = canonical.lower()
            if master_key not in existing_masters:
                skill = SkillMaster(canonical_name=canonical, category_id=cat.id)
                db.add(skill)
                db.flush()
                existing_masters[master_key] = skill
            skill = existing_masters[master_key]

            # 4. Add new Aliases safely
            if canonical.lower() not in [a.lower() for a in aliases]:
                aliases.append(canonical.lower())
                
            for alias in aliases:
                alias_clean = str(alias).lower().strip()
                if alias_clean not in existing_aliases:
                    db.add(SkillAlias(skill_id=skill.id, alias_name=alias_clean))
                    existing_aliases.add(alias_clean)
                    added_count += 1
        
        db.commit()
        logger.info(f"Database seeded successfully! Added {added_count} new aliases.")
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting StackOverflow Dictionary Builder (No API Key Required)...")
    
    # 1. Fetch top 500 tags to start
    raw_tags = fetch_stackoverflow_tags(pages=5, pagesize=100)
    logger.info(f"Fetched {len(raw_tags)} raw tags.")
    
    # 2. Process locally
    processed = process_tags(raw_tags)
    logger.info(f"Filtered down to {len(processed)} valid tech skills.")
    
    # 3. Insert into Database
    seed_database_with_skills(processed)
    logger.info("Done! Run the resume parser to test the new dictionary.")

