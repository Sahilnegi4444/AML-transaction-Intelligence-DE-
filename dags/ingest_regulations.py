"""
AML Transaction Intelligence - Airflow DAG for Regulation Ingestion
====================================================================
Watches data/regulations/ directory and ingests PDFs into pgvector.

Features:
- File sensor for new PDFs
- LangChain + OllamaEmbeddings (nomic-embed-text)
- PostgreSQL pgvector storage
"""

from datetime import datetime, timedelta
from pathlib import Path
import os

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor

# Default args
default_args = {
    'owner': 'aml_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Configuration
CONFIG = {
    "regulations_dir": "/opt/airflow/data/regulations",
    "db_url": "postgresql://aml_user:aml_password@postgres:5432/aml_db",
    "ollama_url": "http://ollama:11434",
    "embedding_model": "nomic-embed-text",
    "chunk_size": 1000,
    "chunk_overlap": 200,
}


def ingest_regulations(**context):
    """Process and embed regulation documents."""
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import OllamaEmbeddings
    import psycopg2
    from psycopg2.extras import execute_values
    import json
    
    print(f"📚 Starting regulation ingestion from {CONFIG['regulations_dir']}")
    
    # Initialize embeddings
    embeddings = OllamaEmbeddings(
        base_url=CONFIG['ollama_url'],
        model=CONFIG['embedding_model'],
    )
    
    # Text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CONFIG['chunk_size'],
        chunk_overlap=CONFIG['chunk_overlap'],
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    
    # Connect to database
    conn = psycopg2.connect(CONFIG['db_url'])
    cursor = conn.cursor()
    
    # Process files
    regulations_path = Path(CONFIG['regulations_dir'])
    processed = 0
    
    for file_path in regulations_path.glob("*"):
        if file_path.suffix.lower() == '.pdf':
            try:
                loader = PyPDFLoader(str(file_path))
                documents = loader.load()
            except Exception as e:
                print(f"   ⚠️ Failed to load PDF {file_path.name}: {e}")
                continue
        elif file_path.suffix.lower() in ['.txt', '.md']:
            try:
                loader = TextLoader(str(file_path))
                documents = loader.load()
            except Exception as e:
                print(f"   ⚠️ Failed to load text {file_path.name}: {e}")
                continue
        else:
            continue
        
        print(f"   📄 Processing: {file_path.name}")
        
        # Split into chunks
        chunks = text_splitter.split_documents(documents)
        print(f"      Created {len(chunks)} chunks")
        
        # Generate embeddings and store
        for idx, chunk in enumerate(chunks):
            try:
                embedding = embeddings.embed_query(chunk.page_content)
                
                # Insert into database
                cursor.execute("""
                    INSERT INTO regulatory_docs 
                    (document_name, chunk_index, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    file_path.name,
                    idx,
                    chunk.page_content,
                    embedding,
                    json.dumps(chunk.metadata) if chunk.metadata else None,
                ))
                
            except Exception as e:
                print(f"      ⚠️ Failed to embed chunk {idx}: {e}")
                continue
        
        conn.commit()
        processed += 1
        print(f"      ✅ Stored {len(chunks)} embeddings")
    
    cursor.close()
    conn.close()
    
    print(f"\n✅ Ingestion complete. Processed {processed} documents.")
    return processed


# DAG Definition
with DAG(
    'ingest_regulations',
    default_args=default_args,
    description='Ingest AML regulations into vector store',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['aml', 'rag', 'embeddings'],
) as dag:
    
    # Task: Ingest regulations
    ingest_task = PythonOperator(
        task_id='ingest_regulations',
        python_callable=ingest_regulations,
        provide_context=True,
    )
    
    ingest_task
