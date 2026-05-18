# Enterprise ATS Resume Parsing Pipeline - System Design

## 1. System Overview
The Enfycon ATS Resume Parser is a production-grade, asynchronous pipeline designed to ingest, extract, normalize, and semantically index candidate resumes at scale. It utilizes a hybrid approach combining traditional NLP (spaCy), deterministic regex pattern matching, and state-of-the-art LLM refinement (Google Gemini) to ensure extremely high fidelity data extraction.

## 2. Core Architecture

The system is built on a microservice-like distributed architecture to handle large volumes of documents (e.g., millions of records) without API bottlenecks.

*   **API Layer (FastAPI):** Exposes endpoints for uploading resumes (`.pdf`, `.docx`) and querying candidates.
*   **Task Queue (Celery + Redis):** Offloads heavy text extraction and LLM inference tasks to asynchronous background workers. Redis acts as the fast, in-memory message broker.
*   **Primary Database (Supabase PostgreSQL):** Stores structured candidate data, raw parsed JSON, skill ontologies, and vector embeddings.
*   **Vector Database (pgvector):** Enables blazing-fast semantic search queries against candidate profiles directly within Postgres.

## 3. The Extraction Pipeline

When a resume is submitted, it passes through a multi-stage funnel:

### Phase 1: Text Ingestion & Section Segmentation
1. The document is converted to raw text.
2. The `ResumeParser` uses deterministic regex to split the text into logical blocks (`experience`, `education`, `skills`, `projects`). It looks for standalone headers (e.g., "PROFESSIONAL BACKGROUND:").

### Phase 2: Local Rule-Based NLP Extraction
1. **spaCy EntityRuler:** A custom NLP pipeline scans for explicit patterns (e.g., matching degrees like "B.Tech", or hardcoded core cloud providers).
2. **Contextual Filtering:** Custom heuristics filter out common resume boilerplate and contact information.
3. **Full-Text Dictionary Scan:** The parser scans the entire document against our massive, RAM-loaded dictionary of Canonical Skills to catch any tech tool missed by traditional NER.

### Phase 3: The LLM Refinement Layer
To guarantee absolute precision, the locally extracted JSON and a chunk of the raw text are passed to **Google Gemini (gemini-3-flash)**.
*   **Zero-Shot Reconstruction:** Gemini acts as an HR Data Scientist, fixing fragmented sentences, standardizing project bullet points, and plucking out subtle skills (e.g., "migrated servers to Terraform").
*   **Data Structure Enforcement:** It strictly formats the response to adhere to the expected JSON schema.

## 4. The StackOverflow Skill Ontology Engine

Instead of relying on a rigid, hardcoded dictionary, the system utilizes a **Self-Assembling Skill Ontology** driven by real-world developer data.

*   **Dynamic Data Sourcing:** A background cron script (`seed_from_stackoverflow.py`) interfaces with the public **StackExchange API**.
*   **Volume:** It pulls the Top 500-2,000 most frequently used developer tags (e.g., `reactjs`, `python-3.x`, `aws`).
*   **Filtration & Normalization:** It utilizes a custom blocklist to drop generic terms (like "arrays" or "json") and transforms developer tags into canonical names and relational aliases.
*   **Database Integration:** It bulk-upserts these into the Supabase `SkillMaster` and `SkillAlias` tables, granting the ATS parser a localized 100% detection rate for virtually all modern technologies.

## 5. Semantic Candidate Search

Traditional Boolean search (e.g., `WHERE skills LIKE '%React%'`) is insufficient for modern recruiting. 
*   **Embeddings Generation:** Once a resume is parsed, its core attributes (skills, experience, education) are concatenated and sent to an Embedding Model (e.g., Google Text Embeddings) to generate a dense numerical vector.
*   **Vector Storage:** The vector is stored in a Supabase `pgvector` column.
*   **Cosine Similarity Matching:** Recruiters can search for "Frontend developer with heavy cloud experience" in natural language. A database stored procedure (`match_resumes`) executes an extremely fast mathematical distance calculation to surface the most contextually relevant candidates.

## 6. Database Schema Highlights

The system relies on a strictly relational architecture for candidate search speed:

*   **`resumes`**: Stores `candidate_name`, `email`, `file_hash` (for deduplication), `parsed_json` (JSONB for NoSQL-like flexibility), and `embedding` (Vector representation).
*   **`skill_categories`**: E.g., "Frontend", "Cloud", "Programming Language".
*   **`skills_master`**: The canonical name of a skill (e.g., "React").
*   **`skill_aliases`**: The 1-to-many variations of how it might appear on a resume (e.g., "reactjs", "react.js", "react").
