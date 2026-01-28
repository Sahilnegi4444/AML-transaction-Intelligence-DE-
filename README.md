# 🏦 AML Transaction Intelligence System

A production-grade, local Anti-Money Laundering (AML) transaction monitoring system with batch analytics, AI-powered explainability, interactive dashboard, and LLM fine-tuning capabilities.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Spark](https://img.shields.io/badge/PySpark-3.5.1-E25A1C)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Ollama](https://img.shields.io/badge/Ollama-llama3.1-green)

---

## ✨ Key Features

- **� Batch Processing**: PySpark for large-scale transaction analysis
- **🤖 RAG-powered Explanations**: AI-generated regulatory analysis citing FATF recommendations
- **� Interactive Dashboard**: Live web dashboard with search, sort, and filter capabilities
- **🧠 Model Fine-tuning**: Unsloth + LoRA for domain-specific AML reasoning
- **� Experiment Tracking**: MLflow for prompt versioning and latency monitoring
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
│  │    Data      │    │   Cleaning   │    │   + pgvector │                   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                   │
│                                                 │                           │
│                    ┌────────────────────────────┼────────────────────┐      │
│                    │                            ▼                    │      │
│  ┌──────────────┐  │                    ┌──────────────┐             │      │
│  │   PySpark    │  │                    │   FastAPI    │◀───┐        │      │
│  │  Detection   │──┼───────────────────▶│   RAG API    │    │        │      │
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
| Anomaly Detection       | PySpark Batch        | Pattern detection engine                |

### AI/ML Stack
| Component               | Technology         | Purpose                       |
|-------------------------|--------------------|-------------------------------|
| LLM Inference           | Ollama (llama3.1)  | Alert explanation generation  |
| Embeddings              | nomic-embed-text   | Document vectorization        |
| Vector Search           | pgvector           | Similarity retrieval          |
| RAG Framework           | LangChain          | Retrieval pipeline            |
| Experiment Tracking     | MLflow 2.10        | Prompt versioning & metrics   |
| Fine-tuning             | Unsloth + LoRA     | Domain-specific training      |

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
│   │   └── HI-Medium_Trans.csv  # Transaction dataset
│   └── regulations/
│       └── *.pdf                # AML regulation documents
├── docs/
│   └── setup_powerbi.md         # Power BI connection guide
├── scripts/
│   ├── clean_and_store.py       # PySpark data cleaning
│   ├── fine_tune_unsloth.py     # Unsloth LoRA fine-tuning
│   ├── init_db.sql              # Database schema
│   ├── interactive_analysis.py  # Model comparison tool
│   └── spark_detect.py          # PySpark detection job
├── docker-compose.yaml          # Infrastructure definition
└── requirements.txt             # Python dependencies
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
docker compose ps  # Verify all services are running
```

### 2. Pull AI Models (one-time)
```powershell
docker compose exec ollama ollama pull llama3.1
docker compose exec ollama ollama pull nomic-embed-text
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run Data Pipeline
```powershell
# Clean and load transaction data (uses PySpark)
docker compose exec --user root spark /opt/spark/bin/spark-submit `
  --packages org.postgresql:postgresql:42.6.0 `
  /opt/spark/work-dir/scripts/clean_and_store.py

# Run anomaly detection
docker compose exec --user root spark /opt/spark/bin/spark-submit `
  --packages org.postgresql:postgresql:42.6.0 `
  /opt/spark/work-dir/scripts/spark_detect.py
```

### 5. Start Dashboard & API
```powershell
# API runs inside Docker
docker compose up -d aml-app

# Start dashboard
python -m http.server 3000 --directory dashboard
```

### 6. Access Services
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

The system detects **suspicious transaction patterns** using PySpark batch processing:

```
Window: 10 minutes per account
Trigger: COUNT(*) > 2  AND  SUM(amount) > $10,000
```

This catches:
- **Structuring (smurfing)**: Multiple rapid transactions
- **Velocity anomalies**: Unusual transaction frequency
- **Large value transfers**: High-risk amounts

---

## 📊 Dashboard Features

The interactive web dashboard provides:

| Feature | Description |
|---------|-------------|
| 🔍 **Search** | Filter alerts by Alert ID or Account |
| 📊 **Sort** | Sort by ID, Amount, Transactions, Risk Score |
| 🎯 **Filter** | Quick filters for High/Medium risk |
| ⏱️ **Timeframe** | Precise date/time range display |
| 🤖 **AI Explain** | Click to generate RAG-based explanations |
| 📈 **Charts** | Top accounts and risk distribution |

---

## 🧠 Model Fine-tuning

Improve AI explanations with domain-specific training:

### Interactive Analysis (No Training Required)
```powershell
python scripts/interactive_analysis.py
```
- Compare Base Model vs Fine-tuned responses
- 5 built-in AML test scenarios
- Custom transaction input support

### Fine-tune with Unsloth (Requires GPU)
```powershell
# Install Unsloth
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install xformers trl peft accelerate bitsandbytes

# Train (50 steps, ~5-10 min)
python scripts/fine_tune_unsloth.py --model_size 3b --max_steps 50
```

---

## 📡 API Endpoints

| Method | Endpoint              | Description                  |
|--------|-----------------------|------------------------------|
| GET    | `/health`             | Service health check         |
| GET    | `/alerts`             | List alerts with pagination  |
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

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

*Built for local, privacy-preserving AML compliance analysis with AI-powered insights.*
