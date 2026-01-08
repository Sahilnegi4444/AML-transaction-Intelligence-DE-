# 🏦 AML Transaction Intelligence System

A production-grade, local Anti-Money Laundering (AML) transaction monitoring system with real-time streaming analytics, AI-powered explainability, and machine learning experiment tracking.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![Kafka](https://img.shields.io/badge/Kafka-3.7-black)
![Spark](https://img.shields.io/badge/Spark-3.5.1-E25A1C)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AML Transaction Intelligence                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Raw CSV    │───▶│    Data      │───▶│  PostgreSQL  │                  │
│  │    Data      │    │  Cleaning    │    │   + pgvector │                   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                   │
│                                                 │                           │
│                    ┌────────────────────────────┼────────────────────┐      │
│                    │                            ▼                    │      │
│  ┌──────────────┐  │  ┌──────────────┐    ┌──────────────┐           │      │
│  │   (KRaft)    │  │  └──────────────┘    └──────┬───────┘           │      │
│  └──────┬───────┘  │                            │                    │      │
│         │          │                            ▼                    │      │
│         ▼          │                    ┌──────────────┐             │      │
│  ┌──────────────┐  │                    │   FastAPI    │◀───┐       │      │
│  │    Spark     │──┼───────────────────▶│   RAG API    │    │       │      │
│  │  Streaming   │  │                    └──────┬───────┘    │       │      │
│  └──────────────┘  │                           │            │       │      │
│                    │         ┌─────────────────┼────────────┤       │      │
│                    │         ▼                 ▼            ▼       │      │
│                    │  ┌──────────────┐  ┌──────────────┐ ┌──────┐  │      │
│                    │  │    Redis     │  │    Ollama    │ │MLflow│  │      │
│                    │  │    Cache     │  │  (llama3.1)  │ │      │  │      │
│                    │  └──────────────┘  └──────────────┘ └──────┘  │      │
│                    │                                                │      │
│                    │  ┌──────────────┐    ┌──────────────┐          │      │
│                    │  │   Airflow    │───▶│  Regulations │          │      │
│                    │  │   Scheduler  │    │  Embeddings  │──────────┘      │
│                    │  └──────────────┘    └──────────────┘                 │
│                    │                                                        │
│                    └────────────Docker Compose Network──────────────────────┘
│                                                                             │
│                    ┌──────────────┐                                         │
│                    │   Power BI   │◀──── localhost:5432                     │
│                    │  Dashboard   │                                         │
│                    └──────────────┘                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Infrastructure
| Component               | Technology                | Purpose                         |
|-------------------------|---------------------------|---------------------------------|
| Container Orchestration | Docker Compose            | Multi-service deployment        |
| Message Broker          | Apache Kafka 3.7 (KRaft)  | Real-time event streaming       |
| Database                | PostgreSQL 16 + pgvector  | Transactional + Vector storage  |
| Cache                   | Redis Alpine              | Hot case retrieval              |
| Workflow                | Apache Airflow 2.8.4      | DAG orchestration               |

### Processing
| Component               | Technology           | Purpose                                 |
|-------------------------|----------------------|-----------------------------------------|
| Stream Processing       | Apache Spark 3.5     | Structured Streaming detection          |
| Data Cleaning           | **PySpark** + JDBC   | Distributed ETL pipeline                |
| Anomaly Detection       | **PySpark** Batch    | Pattern detection engine                |
| Visualization           | Matplotlib + Seaborn | Static analytics charts                 |

### AI/ML Stack
| Component               | Technology        | Purpose                      |
|-------------------------|-------------------|------------------------------|
| LLM Inference           | Ollama (llama3.1) | Alert explanation generation |
| Embeddings              | nomic-embed-text  | Document vectorization       |
| Vector Search           | pgvector          | Similarity retrieval         |
| RAG Framework           | LangChain         | Retrieval pipeline           |
| Experiment Tracking     | MLflow 2.10       | Prompt versioning & metrics  |

### API & Visualization
| Component     | Technology        | Purpose                   |
|---------------|-------------------|---------------------------|
| REST API      | FastAPI           | RAG endpoints             |
| BI Dashboards | Power BI Desktop  | Alert visualization       |

---

## 📁 Project Structure

```
AML Transaction Intelligence/
├── api/
│   └── main.py              # FastAPI RAG application
├── dags/
│   └── ingest_regulations.py # Airflow DAG for embeddings
├── data/
│   ├── raw/
│   │   └── HI-Medium_Trans.csv
│   └── regulations/
│       └── *.pdf            # AML regulation documents
├── docs/
│   └── setup_powerbi.md     # Power BI connection guide
├── output/
│   └── plots/               # Generated visualizations
├── scripts/
│   ├── clean_and_store.py   # Data cleaning pipeline
│   ├── init_db.sql          # Database schema
│   ├── producer.py          # Kafka transaction streamer
│   └── spark_detect.py      # PySpark detection job
├── docker-compose.yaml      # Infrastructure definition
└── requirements.txt         # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop with WSL2 backend
- NVIDIA GPU + Container Toolkit (for Ollama)
- Python 3.11+
- Power BI Desktop (optional)

### 1. Start Infrastructure
```bash
docker compose up -d
docker compose ps  # Verify all services are running
```

### 2. Pull AI Models (one-time)
```bash
docker compose exec ollama ollama pull llama3.1
docker compose exec ollama ollama pull nomic-embed-text
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Data Pipeline
```bash
# Clean and load transaction data
python scripts/clean_and_store.py

# Start Kafka producer
python scripts/producer.py
```

### 5. Start Detection Engine
```bash
docker compose exec spark-master spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.1 \
  /opt/bitnami/spark/scripts/spark_detect.py
```

### 6. Launch API
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔗 Service URLs

| Service           | URL                       | Credentials             |
|-------------------|---------------------------|-------------------------|
| Spark Master UI   | http://localhost:8080     | -                       |
| Airflow           | http://localhost:8082     | admin / admin           |
| MLflow            | http://localhost:5000     | -                       |
| FastAPI Docs      | http://localhost:8000/docs| -                       |
| PostgreSQL        | localhost:5432            | aml_user / aml_password |

---

## 🔍 Detection Logic

The system detects **suspicious transaction patterns** using PySpark:

```
Window: 10 minutes per account
Trigger: COUNT(*) > 2  OR  SUM(amount) > $10,000
```

This catches:
- **Structuring (smurfing)**: Multiple small transactions (count > 2)
- **Large transfers**: Single high-value transactions (total > $10,000)

---

## 📊 API Endpoints

| Method | Endpoint              | Description                 |
|--------|-----------------------|-----------------------------|
| GET    | `/health`             | Service health check        |
| GET    | `/alerts`             | List recent alerts          |
| GET    | `/explain_case/{id}`  | RAG-based alert explanation |
| POST   | `/ingest_regulations` | Index regulatory documents  |

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

*Built for local, privacy-preserving AML compliance analysis.*
