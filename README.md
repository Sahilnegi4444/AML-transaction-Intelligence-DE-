# 🏦 AML Transaction Intelligence System

A production-grade, local Anti-Money Laundering (AML) transaction monitoring system with batch analytics, AI-powered explainability, interactive dashboard, and LLM fine-tuning capabilities.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Spark](https://img.shields.io/badge/PySpark-3.5.1-E25A1C)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Ollama](https://img.shields.io/badge/Ollama-llama3.1-green)

---

## 📊 Pipeline Results

| Metric | Value |
|--------|-------|
| **Total Transactions Processed** | 1,000,000 |
| **Suspicious Alerts Detected** | 36,681 |
| **Detection Rate** | 3.67% |
| **Processing Engine** | SQL + PySpark |

---

## ✨ Key Features

- **📊 Batch Processing**: SQL + PySpark for large-scale transaction analysis (1M+ transactions)
- **🤖 RAG-powered Explanations**: AI-generated regulatory analysis citing FATF recommendations
- **📈 Interactive Dashboard**: Professional web dashboard with search, sort, and filter capabilities
- **🧠 Dynamic Risk Scoring**: Multi-factor risk calculation (transaction count, amount, illicit ratio)
- **📉 Experiment Tracking**: MLflow for prompt versioning and latency monitoring
- **💾 Vector Search**: pgvector for semantic regulatory document retrieval

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AML Transaction Intelligence                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Raw CSV    │───▶│   PySpark    │───▶│  PostgreSQL  │                   │
│  │  (1M rows)   │    │   Cleaning   │    │   + pgvector │                   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                   │
│                                                 │                           │
│                    ┌────────────────────────────┼────────────────────┐      │
│                    │                            ▼                    │      │
│  ┌──────────────┐  │                    ┌──────────────┐             │      │
│  │ SQL Detection│  │                    │   FastAPI    │◀───┐        │      │
│  │ (36K alerts) │──┼───────────────────▶│   RAG API    │    │        │      │
│  └──────────────┘  │                    └──────┬───────┘    │        │      │
│                    │                           │            │        │      │
│                    │         ┌─────────────────┼────────────┤        │      │
│                    │         ▼                 ▼            ▼        │      │
│                    │  ┌──────────────┐  ┌──────────────┐ ┌──────┐   │      │
│                    │  │    Redis     │  │    Ollama    │ │MLflow│   │      │
│                    │  │    Cache     │  │  (llama3.1)  │ │      │   │      │
│                    │  └──────────────┘  └──────────────┘ └──────┘   │      │
│                    │                                                 │      │
│                    └─────────────Docker Compose Network──────────────┘      │
│                                                                             │
│                    ┌──────────────┐    ┌──────────────┐                     │
│                    │  Dashboard   │    │   Power BI   │                     │
│                    │ :3000 (Web)  │    │   :5432      │                     │
│                    └──────────────┘    └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Infrastructure
| Component               | Technology                | Purpose                         |
|-------------------------|---------------------------|---------------------------------|
| Container Orchestration | Docker Compose            | Multi-service deployment        |
| Database                | PostgreSQL 16 + pgvector  | Transactional + Vector storage  |
| Cache                   | Redis Alpine              | Hot case retrieval (<100ms)     |

### Processing
| Component               | Technology           | Purpose                                 |
|-------------------------|----------------------|-----------------------------------------|
| Data Cleaning           | PySpark + JDBC       | Distributed ETL pipeline                |
| Anomaly Detection       | SQL Window Functions | Pattern detection engine                |

### AI/ML Stack
| Component               | Technology         | Purpose                       |
|-------------------------|--------------------|-------------------------------|
| LLM Inference           | Ollama (llama3.1)  | Alert explanation generation  |
| Embeddings              | nomic-embed-text   | Document vectorization        |
| Vector Search           | pgvector           | Similarity retrieval          |
| RAG Framework           | LangChain          | Retrieval pipeline            |
| Experiment Tracking     | MLflow 2.10        | Prompt versioning & metrics   |

### Frontend & Visualization
| Component     | Technology        | Purpose                    |
|---------------|-------------------|----------------------------|
| Web Dashboard | HTML/JS/CSS       | Interactive alert viewer   |
| REST API      | FastAPI           | RAG endpoints              |
| BI Dashboards | Power BI Desktop  | Advanced analytics         |

---

## 📁 Project Structure

```
AML Transaction Intelligence/
├── api/
│   └── main.py                  # FastAPI RAG application
├── dashboard/
│   └── index.html               # Interactive web dashboard
├── data/
│   ├── raw/
│   │   └── HI-Medium_Trans.csv  # Transaction dataset (1M rows)
│   └── regulations/
│       └── *.pdf                # AML regulation documents
├── scripts/
│   ├── clean_and_store.py       # PySpark data cleaning
│   ├── fine_tune_unsloth.py     # Unsloth LoRA fine-tuning
│   ├── init_db.sql              # Database schema
│   ├── interactive_analysis.py  # Model comparison tool
│   └── spark_detect.py          # PySpark detection job
├── docker-compose.yaml
└── requirements.txt
```

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop with WSL2 backend
- NVIDIA GPU + Container Toolkit (for Ollama)
- Python 3.11+

### 1. Start Infrastructure
```powershell
docker compose up -d
docker compose ps  # Verify all services running
```

### 2. Pull AI Models (one-time)
```powershell
docker compose exec ollama ollama pull llama3.1
docker compose exec ollama ollama pull nomic-embed-text
```

### 3. Run Data Pipeline
```powershell
# Clean and load 1M transactions
docker compose exec --user root spark /opt/spark/bin/spark-submit `
  --packages org.postgresql:postgresql:42.6.0 `
  /opt/spark/work-dir/scripts/clean_and_store.py

# Run anomaly detection (generates 36K+ alerts)
docker compose exec postgres psql -U aml_user -d aml_db -f /docker-entrypoint-initdb.d/init_db.sql
```

### 4. Start Dashboard
```powershell
python -m http.server 3000 --directory dashboard
```

### 5. Access Services
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## 🔗 Service URLs

| Service           | URL                       | Credentials             |
|-------------------|---------------------------|-------------------------|
| **Dashboard**     | http://localhost:3000     | -                       |
| **FastAPI Docs**  | http://localhost:8000/docs| -                       |
| Spark Master UI   | http://localhost:8080     | -                       |
| MLflow            | http://localhost:5000     | -                       |
| PostgreSQL        | localhost:5432            | aml_user / aml_password |

---

## 🔍 Detection Logic

**Detection Rule**: (transaction_count > 2) AND (total_amount > $10,000)

**Dynamic Risk Scoring** (0.40 - 1.00):
| Factor | Score Range |
|--------|-------------|
| Transaction Count (3-10+) | +0.10 to +0.30 |
| Amount ($10K-$100K+) | +0.10 to +0.40 |
| Known Illicit Transactions | +0.00 to +0.30 |
| Base Score | +0.20 |

**Results from 1M transactions:**
- **36,681 alerts** detected (3.67% detection rate)
- Risk distribution: min=0.40, avg=0.69, max=1.00

---

## 📊 Dashboard Features

| Feature | Description |
|---------|-------------|
| 🔍 **Search** | Filter alerts by Alert ID or Account |
| 📊 **Sort** | Sort by ID (ascending), Amount, Risk Score |
| 🎯 **Filter** | Quick filters for High/Medium/Low risk |
| 📈 **Charts** | Top accounts and risk distribution |
| 🤖 **AI Explain** | RAG-based explanations with FATF citations |

---

## 📡 API Endpoints

| Method | Endpoint              | Description                  |
|--------|-----------------------|------------------------------|
| GET    | `/health`             | Service health check         |
| GET    | `/alerts?limit=N`     | List alerts (36,681 total)   |
| GET    | `/explain_case/{id}`  | RAG-based alert explanation  |

---

## 🖥️ Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM      | 16GB    | 32GB+       |
| GPU VRAM | 8GB     | 10GB+       |
| Storage  | 50GB    | 100GB SSD   |
| CPU      | 4 cores | 8+ cores    |

---

## 📄 License

MIT License - See LICENSE file for details.

---

*Built for local, privacy-preserving AML compliance analysis with AI-powered insights.*
