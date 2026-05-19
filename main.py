from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import logging
from app.extractor import ResumeExtractor
from app.parser import ResumeParser
from app.embeddings import EmbeddingService
from app.database import save_resume, init_db, get_all_resumes, check_existing_hash
from sentence_transformers import util
import torch
import hashlib
import base64
import json
import re
from celery.result import AsyncResult
from app.tasks import process_resume_task

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enterprise Resume Processor",
    description="Scalable Distributed Resume Extraction Module"
)

# Initialize Embedding Service (Required for Search queries)
embedding_service = EmbeddingService()

# Initialize DB connection only
try:
    init_db() 
except Exception as e:
    logger.warning(f"Database connection issues: {e}")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException

@app.post("/api/v1/extract")
async def extract_resume(file: UploadFile = File(...), metadata: str = Form(None)):
    """
    Primary endpoint for resume extraction.
    Supports PDF, DOCX, and Images. Accepts optional external metadata (e.g., from Dice/Monster).
    """
    logger.info(f"Processing file: {file.filename}")
    content = await file.read()
    filename = file.filename.lower()

    # 0. Duplicate Detection (Active)
    file_hash = hashlib.sha256(content).hexdigest()
    existing = check_existing_hash(file_hash)
    if existing:
        logger.info(f"Duplicate found for hash {file_hash}. Returning existing data.")
        return {
            "status": "completed",
            "db_id": existing.id,
            "data": existing.parsed_json,
            "message": "Resume already exists in database (exact file match)."
        }

    # 1. Parse optional metadata string to dict
    metadata_dict = None
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
            logger.info(f"Received external metadata: {metadata_dict}")
        except Exception as e:
            logger.warning(f"Failed to parse metadata string: {e}")

    # 2. Dispatch Task to Worker
    try:
        content_b64 = base64.b64encode(content).decode('utf-8')
        task = process_resume_task.delay(file.filename, content_b64, file_hash, metadata_dict)
        
        return {
            "status": "accepted",
            "task_id": task.id,
            "filename": file.filename,
            "message": "Resume is being processed in the background."
        }
    except Exception as e:
        logger.error(f"Task dispatch failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue resume for processing.")

@app.get("/api/v1/status/{task_id}")
async def get_task_status(task_id: str):
    """Check the status of a resume processing task."""
    task_result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task_result.status, # PENDING, STARTED, SUCCESS, FAILURE
        "result": None
    }
    
    if task_result.ready():
        response["result"] = task_result.result
        
    return response

@app.get("/api/v1/skills")
async def list_skills_with_aliases():
    """Retrieve all canonical skills and their configured aliases."""
    try:
        from app.database import get_skills_with_aliases
        skills = get_skills_with_aliases()
        return {
            "count": len(skills),
            "skills": skills
        }
    except Exception as e:
        logger.error(f"Failed to fetch skills list: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching skills.")

@app.get("/api/v1/search")
async def search_candidates(query: str = None, keywords: str = None, top_k: int = 10, threshold: float = 0.2):
    """
    Hybrid search across resumes.
    - query: Job Description for semantic search.
    - keywords: Comma-separated list for boolean/keyword filtering.
    """
    results = []
    
    # 1. Semantic Search (JD)
    if query:
        try:
            query_vector = embedding_service.generate_embedding(query)
            from app.database import semantic_search_production
            # Fetch a larger set to allow for keyword filtering
            results = semantic_search_production(query_vector, threshold, limit=top_k * 5)
            logger.info(f"Semantic search found {len(results)} initial candidates.")
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Fallback to all if no JD query
        from app.database import get_all_resumes
        all_recs = get_all_resumes()
        results = []
        for r in all_recs:
            # Ensure p_json is a dict
            p_json = r.parsed_json
            if isinstance(p_json, str):
                import json
                try: p_json = json.loads(p_json)
                except: p_json = {}
                
            results.append({
                "id": r.id, 
                "candidate_name": r.candidate_name, 
                "email": r.email, 
                "parsed_json": p_json,
                "similarity": 1.0 
            })

        
    # 2. Boolean Filtering (Must Include)
    if keywords:
        # 1. Clean the input: replace 'and', '&', and other connectors with commas
        # Also remove any quotation marks that users might add
        clean_keywords = keywords.replace('"', '').replace("'", "")
        clean_keywords = re.sub(r'(?i)\b(and|with|&)\b', ',', clean_keywords)
        
        # 2. Split by comma, pipe, or slash
        if any(d in clean_keywords for d in [',', '|', '/']):
            raw_keyword_list = [k.strip().lower() for k in re.split(r'[,|/]', clean_keywords) if k.strip()]
        else:
            raw_keyword_list = [k.strip().lower() for k in clean_keywords.split() if k.strip()]
        
        from app.normalizer import normalizer
        search_groups = []
        for k in raw_keyword_list:
            group = [k]
            canonical = normalizer.normalize(k)
            if canonical:
                group.append(canonical.lower())
                # Also add versions without dots/slashes for extra resilience
                group.append(canonical.lower().replace('.', '').replace('/', ''))
            search_groups.append(list(set(group))) # Unique terms only
        
        logger.info(f"--- BOOLEAN SEARCH DEBUG ---")
        logger.info(f"Query Groups: {search_groups}")
        
        filtered_results = []
        for res in results:
            # Create an extreme search blob
            p_json = res.get("parsed_json", {}) or {}
            if isinstance(p_json, str):
                import json
                try: p_json = json.loads(p_json)
                except: p_json = {}
            
            # Flatten everything: Name, Email, Roles, and ALL Skills
            skills_str = " ".join(p_json.get("skills", []))
            roles_str = " ".join(p_json.get("experience", {}).get("detected_roles", []))
            blob = f"{res.get('candidate_name', '')} {res.get('email', '')} {skills_str} {roles_str}".lower()
            
            # Match logic
            matches_all = True
            for group in search_groups:
                if not any(term in blob for term in group):
                    matches_all = False
                    break
            
            if matches_all:
                filtered_results.append(res)
        
        logger.info(f"Filtered results: {len(filtered_results)} candidates.")
        results = filtered_results

    # 3. Final Scoring & Truncation
    # Convert similarity to 0-100 score
    from app.database import SessionLocal, Candidate
    db_session = SessionLocal()
    try:
        for res in results:
            res["score"] = round(res.get("similarity", 0) * 100, 1)
            # Clean up sensitive data for UI
            if "embedding" in res: del res["embedding"]
            
            # Enrich with Candidate table columns
            email = res.get("email")
            candidate = db_session.query(Candidate).filter(Candidate.email == email).first() if email else None
            if candidate:
                res["work_authorization"] = candidate.work_authorization
                res["location"] = candidate.raw_current_location
                res["total_experience_years"] = candidate.total_experience_years
            else:
                res["work_authorization"] = None
                res["location"] = None
                res["total_experience_years"] = None
    finally:
        db_session.close()

    # Sort by score and limit
    results = sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

    return {
        "count": len(results),
        "results": results
    }

@app.get("/search", response_class=HTMLResponse)
async def search_page():
    """Premium Search Dashboard UI."""
    return r"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Candidate Search | AI ATS</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            :root { --bg: #0f172a; --card: #1e293b; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; }
            body { font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 2rem; }
            .container { max-width: 1000px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 3rem; }
            h1 { font-size: 2.5rem; color: var(--accent); margin-bottom: 0.5rem; }
            
            .search-box { background: var(--card); padding: 2rem; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); margin-bottom: 2rem; border: 1px solid #334155; }
            .input-group { margin-bottom: 1.5rem; text-align: left; }
            label { display: block; margin-bottom: 0.5rem; color: var(--muted); font-weight: 600; }
            textarea, input { width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.8rem; color: white; font-family: inherit; box-sizing: border-box; }
            textarea { height: 120px; resize: vertical; }
            .btn-search { background: var(--accent); color: var(--bg); border: none; padding: 1rem 2rem; border-radius: 8px; font-weight: 700; cursor: pointer; width: 100%; font-size: 1.1rem; transition: transform 0.2s; }
            .btn-search:hover { transform: translateY(-2px); background: #7dd3fc; }

            .results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid #334155; padding-bottom: 1rem; }
            .candidate-card { background: var(--card); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s; border-left: 4px solid transparent; }
            .candidate-card:hover { transform: scale(1.01); background: #2d3748; border-left-color: var(--accent); }
            .info h3 { margin: 0; font-size: 1.3rem; color: var(--accent); }
            .info p { margin: 0.5rem 0 0; color: var(--muted); }
            
            .score-badge { background: rgba(56, 189, 248, 0.1); border: 1px solid var(--accent); color: var(--accent); padding: 0.5rem 1rem; border-radius: 20px; font-weight: 700; font-size: 1.2rem; }
            .skill-tag { display: inline-block; background: #334155; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; margin-right: 0.4rem; margin-top: 0.5rem; border: 1px solid transparent; }
            .skill-tag.matched { background: rgba(56, 189, 248, 0.2); border-color: var(--accent); color: white; font-weight: 600; box-shadow: 0 0 10px rgba(56, 189, 248, 0.3); }
            
            .badge { display: inline-block; padding: 0.3rem 0.7rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; margin-right: 0.5rem; margin-top: 0.5rem; border: 1px solid transparent; }
            .visa-badge { background: rgba(56, 189, 248, 0.15); border-color: var(--accent); color: var(--accent); }
            .loc-badge { background: rgba(244, 63, 94, 0.15); border-color: #f43f5e; color: #f43f5e; }
            .exp-badge { background: rgba(168, 85, 247, 0.15); border-color: #a855f7; color: #a855f7; }
            
            #loader { display: none; text-align: center; padding: 2rem; color: var(--accent); font-weight: bold; }
            .empty-state { text-align: center; padding: 4rem; color: var(--muted); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>AI Talent Discovery</h1>
                <p>Rank 5,000,000+ candidates using Semantic & Boolean Intelligence</p>
            </div>

            <div class="search-box">
                <div class="input-group">
                    <label>Job Description (Semantic Match)</label>
                    <textarea id="jdInput" placeholder="Paste the job description here for AI-powered matching..."></textarea>
                </div>
                <div class="input-group">
                    <label>Boolean Search / Keywords (Must include)</label>
                    <input type="text" id="keywordInput" placeholder="e.g. Python, AWS, Remote, Manager">
                </div>
                <button onclick="performSearch()" class="btn-search">Find Top 10 Candidates</button>
            </div>

            <div id="loader">Scanning 5,000,000 resumes...</div>

            <div id="resultsContainer">
                <!-- Results populated here -->
            </div>
        </div>

        <script>
            async function performSearch() {
                const jd = document.getElementById('jdInput').value;
                const keywords = document.getElementById('keywordInput').value;
                const loader = document.getElementById('loader');
                const container = document.getElementById('resultsContainer');

                if (!jd && !keywords) return alert('Enter a JD or Keywords to search');

                loader.style.display = 'block';
                container.innerHTML = '';

                try {
                    const response = await fetch(`/api/v1/search?query=${encodeURIComponent(jd)}&keywords=${encodeURIComponent(keywords)}`);
                    const data = await response.json();
                    loader.style.display = 'none';

                    if (data.results.length === 0) {
                        container.innerHTML = '<div class="empty-state">No matching candidates found. Try adjusting your filters.</div>';
                        return;
                    }

                    container.innerHTML = `
                        <div class="results-header">
                            <h2>Top ${data.results.length} Matches</h2>
                            <span style="color:var(--muted)">Found ${data.count} candidates</span>
                        </div>
                    `;

                    const queryTokens = (jd + " " + keywords).toLowerCase().split(/[\s,]+/);

                    data.results.forEach(res => {
                        const skills = res.parsed_json.skills.map(s => {
                            const isMatch = queryTokens.some(token => token.length > 2 && s.toLowerCase().includes(token));
                            return `<span class="skill-tag ${isMatch ? 'matched' : ''}">${s}</span>`;
                        }).join('');
                        
                        const card = `
                            <div class="candidate-card">
                                <div class="info">
                                    <h3>${res.candidate_name || 'Anonymous Candidate'}</h3>
                                    <p>${res.email || 'No email provided'}</p>
                                    <div style="margin-top:0.5rem; display: flex; flex-wrap: wrap;">
                                        ${res.work_authorization ? `<span class="badge visa-badge">${res.work_authorization}</span>` : ''}
                                        ${res.location ? `<span class="badge loc-badge">📍 ${res.location}</span>` : ''}
                                        ${res.total_experience_years ? `<span class="badge exp-badge">💼 ${res.total_experience_years} Yrs Exp</span>` : ''}
                                    </div>
                                    <div style="margin-top:0.8rem">${skills}</div>
                                </div>
                                <div class="score-badge">${res.score}% Match</div>
                            </div>
                        `;
                        container.innerHTML += card;
                    });
                } catch (error) {
                    loader.style.display = 'none';
                    alert('Search failed. Please try again.');
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
async def home():
    """Simple UI for testing uploads."""
    return r"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ATS Resume Extractor</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
            .container { background: #1e293b; padding: 2rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 100%; max-width: 500px; text-align: center; }
            h1 { color: #38bdf8; margin-bottom: 0.5rem; }
            p { color: #94a3b8; margin-bottom: 2rem; }
            .upload-box { border: 2px dashed #334155; padding: 2rem; border-radius: 8px; cursor: pointer; transition: all 0.3s; }
            .upload-box:hover { border-color: #38bdf8; background: #1e293b; }
            input[type="file"] { display: none; }
            .btn { background: #38bdf8; color: #0f172a; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 1rem; width: 100%; }
            .btn:hover { background: #0ea5e9; }
            #result { margin-top: 2rem; text-align: left; background: #0f172a; padding: 1rem; border-radius: 6px; font-size: 0.85rem; display: none; max-height: 400px; overflow-y: auto; }
            pre { white-space: pre-wrap; word-wrap: break-word; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ATS Extraction</h1>
            <p>Upload a PDF, Word, or Scanned Resume</p>
            <form id="uploadForm">
                <label class="upload-box" for="resumeFile">
                    <div id="fileName">Click to choose file or drag here</div>
                    <input type="file" id="resumeFile" name="file" accept=".pdf,.docx,.png,.jpg,.jpeg">
                </label>
                <button type="submit" class="btn">Process Resume</button>
            </form>
            <div id="result">
                <h3 style="color:#38bdf8">Parsed JSON Result:</h3>
                <pre id="jsonContent"></pre>
            </div>
        </div>

        <script>
            const fileInput = document.getElementById('resumeFile');
            const fileNameDisplay = document.getElementById('fileName');
            const form = document.getElementById('uploadForm');
            const resultBox = document.getElementById('result');
            const jsonContent = document.getElementById('jsonContent');

            fileInput.addEventListener('change', (e) => {
                if(e.target.files.length > 0) {
                    fileNameDisplay.textContent = e.target.files[0].name;
                }
            });

            form.onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData();
                if(fileInput.files.length === 0) return alert('Select a file');
                
                formData.append('file', fileInput.files[0]);
                fileNameDisplay.textContent = "Processing...";
                
                try {
                    const response = await fetch('/api/v1/extract', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    resultBox.style.display = 'block';
                    jsonContent.textContent = JSON.stringify(data, null, 2);
                    fileNameDisplay.textContent = fileInput.files[0].name;

                    // If it's a new task, start polling for the result
                    if (data.status === 'accepted') {
                        pollStatus(data.task_id);
                    }
                } catch (error) {
                    alert('Error processing resume');
                    fileNameDisplay.textContent = "Error occurred";
                }
            };

            async function pollStatus(taskId) {
                const interval = setInterval(async () => {
                    const response = await fetch(`/api/v1/status/${taskId}`);
                    const statusData = await response.json();
                    
                    jsonContent.textContent = "Processing background task... Status: " + statusData.status + "\\n" + JSON.stringify(statusData, null, 2);
                    
                    if (statusData.status === 'SUCCESS' || statusData.status === 'FAILURE') {
                        clearInterval(interval);
                        jsonContent.textContent = JSON.stringify(statusData.result, null, 2);
                    }
                }, 2000);
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
