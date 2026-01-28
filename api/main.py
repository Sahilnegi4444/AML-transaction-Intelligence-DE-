"""
AML Transaction Intelligence - FastAPI Application
===================================================
RAG-based alert explanation with caching and experiment tracking.

Features:
- /explain_case/{alert_id}: Redis-cached RAG explanation
- /ingest_regulations: Manual trigger for document ingestion
- /health: Health check endpoint
- MLflow tracking for prompt performance
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

# Configuration
CONFIG = {
    "db_url": {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "database": os.getenv("POSTGRES_DB", "aml_db"),
        "user": os.getenv("POSTGRES_USER", "aml_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "aml_password"),
    },
    "redis_url": os.getenv("REDIS_URL", "localhost"),
    "redis_port": int(os.getenv("REDIS_PORT", 6379)),
    "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
    "llm_model": "llama3.1",
    "embedding_model": "nomic-embed-text",
    "mlflow_uri": os.getenv("MLFLOW_URI", "http://localhost:5000"),
    "cache_ttl": 3600,  # 1 hour
    "prompt_version": "v1.0",
}

# Initialize FastAPI
app = FastAPI(
    title="AML Transaction Intelligence API",
    description="RAG-based alert explanation service with caching and experiment tracking",
    version="1.0.0",
)

# Enable CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response models
class ExplanationResponse(BaseModel):
    alert_id: int
    explanation: str
    relevant_regulations: list
    risk_assessment: str
    cached: bool
    latency_ms: int
    prompt_version: str


class HealthResponse(BaseModel):
    status: str
    services: dict
    timestamp: str


class IngestResponse(BaseModel):
    status: str
    documents_processed: int
    chunks_created: int


# Database connection
def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(**CONFIG["db_url"], cursor_factory=RealDictCursor)


# Redis connection
def get_redis_client():
    """Create Redis connection."""
    return redis.Redis(
        host=CONFIG["redis_url"],
        port=CONFIG["redis_port"],
        decode_responses=True,
    )


def check_ollama_available() -> bool:
    """Check if Ollama is available."""
    try:
        response = requests.get(f"{CONFIG['ollama_url']}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def get_embedding(text: str) -> list:
    """Generate embedding using Ollama."""
    response = requests.post(
        f"{CONFIG['ollama_url']}/api/embeddings",
        json={
            "model": CONFIG["embedding_model"],
            "prompt": text,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def similarity_search(embedding: list, top_k: int = 3) -> list:
    """Search for similar regulatory documents."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # pgvector similarity search
    cursor.execute("""
        SELECT 
            document_name,
            content,
            1 - (embedding <=> %s::vector) as similarity
        FROM regulatory_docs
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding, embedding, top_k))
    
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [dict(r) for r in results]


def generate_explanation(alert_data: dict, regulations: list) -> str:
    """Generate explanation using Ollama LLM."""
    
    # Construct prompt
    reg_text = "\n\n".join([
        f"**{r['document_name']}** (Relevance: {r['similarity']:.2%}):\n{r['content']}"
        for r in regulations
    ])
    
    prompt = f"""You are an AML (Anti-Money Laundering) compliance expert. Analyze the following suspicious activity alert and explain why it may indicate potential money laundering.

## Alert Details
- **Alert Type**: {alert_data.get('alert_type', 'Unknown')}
- **Account**: {alert_data.get('source_account', 'Unknown')}
- **Transaction Count**: {alert_data.get('transaction_count', 0)}
- **Total Amount**: ${alert_data.get('total_amount', 0):,.2f}
- **Average Amount**: ${alert_data.get('avg_amount', 0):,.2f}
- **Time Window**: {alert_data.get('window_start')} to {alert_data.get('window_end')}
- **Risk Score**: {alert_data.get('risk_score', 'N/A')}

## Relevant AML Regulations
{reg_text}

## Instructions
1. Identify which specific red flag patterns are present
2. Reference the relevant regulations
3. Assess the risk level (Low/Medium/High/Critical)
4. Recommend next steps for investigation

Provide a clear, professional explanation suitable for a compliance officer."""

    # Call Ollama
    response = requests.post(
        f"{CONFIG['ollama_url']}/api/generate",
        json={
            "model": CONFIG["llm_model"],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 1024,
            }
        },
        timeout=120,
    )
    response.raise_for_status()
    
    return response.json()["response"]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of all services."""
    services = {}
    
    # Check PostgreSQL
    try:
        conn = get_db_connection()
        conn.close()
        services["postgres"] = "healthy"
    except Exception as e:
        services["postgres"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        r = get_redis_client()
        r.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    # Check Ollama
    if check_ollama_available():
        services["ollama"] = "healthy"
    else:
        services["ollama"] = "unhealthy: not reachable"
    
    overall = "healthy" if all("healthy" in v for v in services.values()) else "degraded"
    
    return HealthResponse(
        status=overall,
        services=services,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/explain_case/{alert_id}", response_model=ExplanationResponse)
async def explain_case(alert_id: int):
    """
    Generate RAG-based explanation for an alert.
    
    Flow:
    1. Check Redis cache
    2. Fetch alert from PostgreSQL
    3. Vector similarity search for regulations
    4. Generate explanation with Ollama
    5. Log to MLflow
    6. Cache result
    """
    start_time = time.time()
    cache_key = f"alert_explanation:{alert_id}:{CONFIG['prompt_version']}"
    
    # Step 1: Check Redis cache
    try:
        redis_client = get_redis_client()
        cached = redis_client.get(cache_key)
        if cached:
            result = json.loads(cached)
            result["cached"] = True
            result["latency_ms"] = int((time.time() - start_time) * 1000)
            return ExplanationResponse(**result)
    except Exception as e:
        print(f"Redis cache check failed: {e}")
    
    # Step 2: Fetch alert from database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alerts WHERE id = %s", (alert_id,))
        alert = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        alert_data = dict(alert)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    
    # Step 3: Vector similarity search
    try:
        # Create query embedding from alert description
        query_text = f"{alert_data.get('alert_type', '')} {alert_data.get('source_account', '')} transactions totaling ${alert_data.get('total_amount', 0)}"
        embedding = get_embedding(query_text)
        regulations = similarity_search(embedding, top_k=3)
    except Exception as e:
        print(f"Similarity search failed: {e}")
        regulations = []
    
    # Step 4: Generate explanation with Ollama
    try:
        if not check_ollama_available():
            raise HTTPException(status_code=503, detail="Ollama LLM service unavailable")
        
        explanation = generate_explanation(alert_data, regulations)
        
        # Extract risk level from explanation (simple heuristic)
        risk_levels = ["Critical", "High", "Medium", "Low"]
        risk_assessment = "Medium"  # Default
        for level in risk_levels:
            if level.lower() in explanation.lower():
                risk_assessment = level
                break
                
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"LLM generation failed: {e}")
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Step 5: Log to MLflow (optional)
    if MLFLOW_AVAILABLE:
        try:
            mlflow.set_tracking_uri(CONFIG["mlflow_uri"])
            mlflow.set_experiment("aml_case_explanations")
            
            with mlflow.start_run(run_name=f"alert_{alert_id}"):
                mlflow.log_params({
                    "alert_id": alert_id,
                    "prompt_version": CONFIG["prompt_version"],
                    "llm_model": CONFIG["llm_model"],
                })
                mlflow.log_metrics({
                    "latency_ms": latency_ms,
                    "regulations_found": len(regulations),
                })
                mlflow.log_text(explanation, "explanation.txt")
        except Exception as e:
            print(f"MLflow logging failed: {e}")
    
    # Prepare result
    result = {
        "alert_id": alert_id,
        "explanation": explanation,
        "relevant_regulations": [r["document_name"] for r in regulations],
        "risk_assessment": risk_assessment,
        "cached": False,
        "latency_ms": latency_ms,
        "prompt_version": CONFIG["prompt_version"],
    }
    
    # Step 6: Cache result in Redis
    try:
        redis_client.setex(
            cache_key,
            CONFIG["cache_ttl"],
            json.dumps(result),
        )
    except Exception as e:
        print(f"Redis caching failed: {e}")
    
    return ExplanationResponse(**result)


@app.post("/ingest_regulations", response_model=IngestResponse)
async def ingest_regulations(background_tasks: BackgroundTasks):
    """
    Manually trigger regulation document ingestion.
    Processes PDFs and text files from data/regulations/.
    """
    from pathlib import Path
    import PyPDF2
    
    regulations_dir = Path("data/regulations")
    if not regulations_dir.exists():
        raise HTTPException(status_code=404, detail="Regulations directory not found")
    
    documents_processed = 0
    chunks_created = 0
    
    # Ensure regulatory_docs table has correct schema
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_docs (
                id SERIAL PRIMARY KEY,
                document_name TEXT,
                chunk_index INTEGER,
                content TEXT NOT NULL,
                embedding vector(768)
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Table creation warning: {e}")
    cursor.close()
    conn.close()
    
    def sanitize_text(text: str) -> str:
        """Remove NUL characters and other problematic chars."""
        if text:
            return text.replace('\x00', '').replace('\0', '').strip()
        return ""
    
    for file_path in regulations_dir.glob("*"):
        if file_path.suffix.lower() not in ['.pdf', '.txt', '.md']:
            continue
            
        try:
            content = ""
            
            # Handle PDF files
            if file_path.suffix.lower() == '.pdf':
                try:
                    with open(file_path, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        for page in pdf_reader.pages:
                            page_text = page.extract_text() or ""
                            content += sanitize_text(page_text) + "\n"
                except Exception as e:
                    print(f"PDF read error for {file_path.name}: {e}")
                    continue
            else:
                # Handle text/markdown files
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = sanitize_text(f.read())
            
            if not content.strip():
                print(f"No content extracted from {file_path.name}")
                continue
            
            # Simple chunking with overlap
            chunk_size = 800
            overlap = 100
            chunks = []
            start = 0
            while start < len(content):
                chunk = content[start:start + chunk_size]
                chunk = sanitize_text(chunk)
                if chunk:
                    chunks.append(chunk)
                start += chunk_size - overlap
            
            print(f"Processing {file_path.name}: {len(chunks)} chunks")
            
            # Store in database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for idx, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                try:
                    embedding = get_embedding(chunk)
                    
                    cursor.execute("""
                        INSERT INTO regulatory_docs 
                        (document_name, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s)
                    """, (file_path.name, idx, chunk, embedding))
                    
                    chunks_created += 1
                except Exception as e:
                    print(f"Failed to embed chunk {idx}: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            documents_processed += 1
            print(f"Completed {file_path.name}: {chunks_created} chunks total")
            
        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")
    
    return IngestResponse(
        status="completed",
        documents_processed=documents_processed,
        chunks_created=chunks_created,
    )


@app.get("/alerts")
async def list_alerts(limit: int = 20, offset: int = 0, status: Optional[str] = None):
    """List alerts with pagination and optional status filter."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total count first
    count_query = "SELECT COUNT(*) as total FROM alerts"
    count_params = []
    if status:
        count_query += " WHERE status = %s"
        count_params.append(status)
    
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()['total']
    
    # Get alerts with limit and offset
    query = "SELECT * FROM alerts"
    params = []
    
    if status:
        query += " WHERE status = %s"
        params.append(status)
    
    # Use ID sorting for consistent pagination
    query += " ORDER BY id ASC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    alerts = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return {
        "alerts": [dict(a) for a in alerts], 
        "total": total_count,
        "returned": len(alerts),
        "limit": limit,
        "offset": offset
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
