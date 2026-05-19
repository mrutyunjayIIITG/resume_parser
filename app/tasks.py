from app.celery_app import celery_app
from app.extractor import ResumeExtractor
from app.parser import ResumeParser
from app.embeddings import EmbeddingService
from app.database import save_resume
import logging

logger = logging.getLogger(__name__)

# Initialize models globally so they load once when worker starts
embedding_service = EmbeddingService()

@celery_app.task(name="app.tasks.process_resume_task", bind=True)
def process_resume_task(self, filename: str, content_b64: str, file_hash: str, metadata: dict = None):
    """
    Background task to process a resume.
    Arguments:
        filename: Name of the file
        content_b64: Base64 encoded file content (since Celery needs serializable args)
        file_hash: The pre-calculated SHA256 hash
        metadata: Optional dictionary of external metadata (e.g. from Dice/Monster)
    """
    import base64
    content = base64.b64decode(content_b64)
    
    try:
        # 1. Extraction
        if filename.endswith(".pdf"):
            text = ResumeExtractor.extract_from_pdf(content)
        elif filename.endswith(".docx"):
            text = ResumeExtractor.extract_from_docx(content)
        else:
            text = ResumeExtractor.extract_from_image(content)

        # 2. Parsing
        logger.info(f"Starting parse for {filename}. Text length: {len(text)}")
        if len(text.strip()) < 10:
            logger.warning(f"Extracted text is too short: '{text}'")
            
        result = ResumeParser.parse(text)

        # Merge external metadata (e.g., from Dice/Monster) into the parsed result
        if metadata and isinstance(metadata, dict):
            logger.info(f"Merging external metadata into parsed result: {metadata}")
            
            # Merge Work Authorization (Highest priority)
            if "work_authorization" in metadata and metadata["work_authorization"]:
                result["work_authorization"] = metadata["work_authorization"]
                
            # Merge Location (Highest priority)
            if "location" in metadata and metadata["location"]:
                loc_val = metadata["location"]
                if "ats_normalized" not in result:
                    result["ats_normalized"] = {}
                from app.normalizer import normalizer
                loc_id, loc_canon = normalizer.normalize_location(loc_val)
                result["ats_normalized"]["location"] = {
                    "id": loc_id,
                    "raw": loc_val,
                    "canonical": loc_canon or loc_val
                }

            # Merge other custom sourcing fields
            for custom_field in ["target_rate", "availability", "tax_terms", "relocation_willingness"]:
                if custom_field in metadata:
                    result[custom_field] = metadata[custom_field]

        # 3. Embedding
        vector = embedding_service.generate_resume_vector(result)

        # 4. Identity Check & Persistence
        contact = result.get("contact", {}) if isinstance(result, dict) else {}
        emails = []
        if isinstance(contact, dict):
            emails = contact.get("emails", [])
        elif isinstance(contact, list):
            # If contact is a flat list, filter out anything containing '@'
            emails = [item for item in contact if isinstance(item, str) and "@" in item]
            
        if not isinstance(emails, list):
            emails = [emails] if isinstance(emails, str) else []
            
        primary_email = emails[0] if emails else None
        
        from app.database import check_existing_email
        existing = check_existing_email(primary_email)
        if existing:
            logger.info(f"Duplicate candidate found by email: {primary_email}")
            return {
                "status": "completed",
                "db_id": existing.id,
                "data": existing.parsed_json,
                "message": f"Candidate with email {primary_email} already exists."
            }

        db_id = save_resume(filename, result, vector, file_hash, raw_text=text, source="API Upload")

        return {
            "status": "completed",
            "db_id": db_id,
            "data": result
        }

    except Exception as e:
        logger.error(f"Task failed for {filename}: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }
