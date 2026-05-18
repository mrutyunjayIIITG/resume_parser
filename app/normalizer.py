from app.database import SessionLocal, SkillMaster, SkillAlias, LocationMaster, LocationAlias, DesignationMaster, DesignationAlias, CompanyMaster, CompanyAlias, DegreeMaster, DegreeAlias
import logging

logger = logging.getLogger(__name__)

class EntityNormalizer:
    _instance = None
    _alias_map = {}
    
    # New Maps (mapping alias -> (id, canonical_name))
    _location_map = {}
    _designation_map = {}
    _company_map = {}
    _degree_map = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EntityNormalizer, cls).__new__(cls)
            cls._instance._load_dictionary()
        return cls._instance

    def _load_dictionary(self):
        """Loads all aliases into RAM-based hashmaps from the database."""
        db = SessionLocal()
        try:
            # 1. Skills
            query = db.query(SkillAlias.alias_name, SkillMaster.canonical_name)\
                      .join(SkillMaster, SkillAlias.skill_id == SkillMaster.id).all()
            self._alias_map = {row.alias_name: row.canonical_name for row in query}
            
            # 2. Locations
            loc_query = db.query(LocationAlias.alias, LocationMaster.id, LocationMaster.canonical_location)\
                          .join(LocationMaster, LocationAlias.location_id == LocationMaster.id).all()
            self._location_map = {row.alias.lower(): (row.id, row.canonical_location) for row in loc_query}

            # 3. Designations
            des_query = db.query(DesignationAlias.alias, DesignationMaster.id, DesignationMaster.canonical_designation)\
                          .join(DesignationMaster, DesignationAlias.designation_id == DesignationMaster.id).all()
            self._designation_map = {row.alias.lower(): (row.id, row.canonical_designation) for row in des_query}

            # 4. Companies
            com_query = db.query(CompanyAlias.alias, CompanyMaster.id, CompanyMaster.canonical_company_name)\
                          .join(CompanyMaster, CompanyAlias.company_id == CompanyMaster.id).all()
            self._company_map = {row.alias.lower(): (row.id, row.canonical_company_name) for row in com_query}

            # 5. Degrees
            deg_query = db.query(DegreeAlias.alias, DegreeMaster.id, DegreeMaster.canonical_degree)\
                          .join(DegreeMaster, DegreeAlias.degree_id == DegreeMaster.id).all()
            self._degree_map = {row.alias.lower(): (row.id, row.canonical_degree) for row in deg_query}

            logger.info(f"Entity Normalizer loaded: {len(self._alias_map)} skills, {len(self._location_map)} locations, {len(self._designation_map)} designations, {len(self._company_map)} companies, {len(self._degree_map)} degrees.")
        except Exception as e:
            logger.error(f"Failed to load dictionaries: {e}")
        finally:
            db.close()

    def normalize(self, raw_skill: str):
        """Maps a raw skill string to its canonical version."""
        return self._alias_map.get(raw_skill.lower().strip())

    def process_list(self, raw_skills: list):
        """Normalizes a list of skills and returns unique canonical names."""
        canonical_skills = set()
        for s in raw_skills:
            normalized = self.normalize(s)
            if normalized:
                canonical_skills.add(normalized)
            else:
                if len(s) > 1:
                    canonical_skills.add(s.title())
        return sorted(list(canonical_skills))

    # Generic normalizer helper
    def _normalize_entity(self, raw_text: str, map_dict: dict):
        if not raw_text: return None, None
        key = raw_text.lower().strip()
        if key in map_dict:
            return map_dict[key] # returns (id, canonical)
        return None, None

    def normalize_location(self, raw_loc: str):
        return self._normalize_entity(raw_loc, self._location_map)

    def normalize_designation(self, raw_des: str):
        return self._normalize_entity(raw_des, self._designation_map)

    def normalize_company(self, raw_com: str):
        return self._normalize_entity(raw_com, self._company_map)
        
    def normalize_degree(self, raw_deg: str):
        return self._normalize_entity(raw_deg, self._degree_map)

# Singleton instance
normalizer = EntityNormalizer()
