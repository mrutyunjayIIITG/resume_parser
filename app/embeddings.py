from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None

    def generate_embedding(self, text: str):
        """Generates a 384-dimensional vector for the given text."""
        if not self.model:
            return None
        
        # We truncate long resumes to avoid context window issues
        truncated_text = text[:2000] 
        embedding = self.model.encode(truncated_text)
        return embedding.tolist()

    def generate_resume_vector(self, parsed_data: dict):
        """
        Creates a weighted vector based on Skills and Experience.
        This is what we store for Semantic Search.
        """
        if not isinstance(parsed_data, dict):
            return self.generate_embedding("")
            
        skills = parsed_data.get("skills", [])
        if not isinstance(skills, list):
            skills = []
        skills_str = ", ".join([str(s) for s in skills if s])
        
        experience = parsed_data.get("experience", {})
        roles = []
        if isinstance(experience, dict):
            roles = experience.get("detected_roles", [])
        elif isinstance(experience, list):
            for exp in experience:
                if isinstance(exp, dict):
                    title = exp.get("role") or exp.get("job_title") or exp.get("title")
                    if title: roles.append(title)
                elif isinstance(exp, str):
                    roles.append(exp)
                    
        if not isinstance(roles, list):
            roles = []
        roles_str = ", ".join([str(r) for r in roles if r])
        
        combined_text = f"Skills: {skills_str}. Experience: {roles_str}."
        return self.generate_embedding(combined_text)
