import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.database import SessionLocal, LocationMaster, LocationAlias
import geonamescache

def seed_real_locations():
    print("Connecting to database...")
    db = SessionLocal()
    print("Database connected.")
    print("Loading GeonamesCache...")
    gc = geonamescache.GeonamesCache()
    print("GeonamesCache loaded.")
    
    print("Fetching world cities...")
    cities = gc.get_cities()
    
    # Filter for US and IN cities with population > 50,000 for ATS relevance
    target_countries = ['US', 'IN', 'GB', 'CA', 'AU'] # US, India, UK, Canada, Australia
    relevant_cities = [c for c in cities.values() if c['countrycode'] in target_countries and c['population'] > 50000]
    
    print(f"Found {len(relevant_cities)} relevant major cities. Seeding to database...")
    
    added_count = 0
    try:
        for c in relevant_cities:
            city_name = c['name']
            country = c['countrycode']
            state = c.get('admin1code', 'Unknown')
            
            # Check if canonical location already exists
            loc = db.query(LocationMaster).filter_by(canonical_location=city_name).first()
            if not loc:
                loc = LocationMaster(canonical_location=city_name, country=country, state=state)
                db.add(loc)
                db.flush()
                added_count += 1
                
            # Add alias (lowercase version)
            alias_name = city_name.lower()
            if not db.query(LocationAlias).filter_by(alias=alias_name).first():
                db.add(LocationAlias(alias=alias_name, location_id=loc.id))
                
            # For Indian cities, add common ATS aliases manually if applicable
            manual_aliases = []
            if city_name == "Bengaluru":
                manual_aliases = ["bangalore", "blr", "bengalooru"]
            elif city_name == "Mumbai":
                manual_aliases = ["bombay", "navi mumbai"]
            elif city_name == "Chennai":
                manual_aliases = ["madras"]
            elif city_name == "New York City":
                manual_aliases = ["new york", "nyc", "ny"]
            elif city_name == "San Francisco":
                manual_aliases = ["sf", "san francisco bay area", "sf bay area"]
            
            for ma in manual_aliases:
                if not db.query(LocationAlias).filter_by(alias=ma).first():
                    db.add(LocationAlias(alias=ma, location_id=loc.id))
            
            # Commit in batches to prevent Supabase connection timeout
            if added_count % 100 == 0:
                db.commit()
                    
        db.commit()
        print(f"Successfully seeded {added_count} new real locations and aliases into the ATS database!")
    except Exception as e:
        db.rollback()
        print(f"Failed to seed locations: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_real_locations()
