"""
AML Transaction Intelligence - Kafka Producer
==============================================
Streams transactions from PostgreSQL to Kafka topic.

Features:
- Reads from transactions table or CSV fallback
- Streams JSON events to 'aml_stream' topic
- Configurable batch size and rate limiting
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer
from kafka.errors import KafkaError
from sqlalchemy import create_engine, text

# Configuration - uses environment variables for Docker compatibility
CONFIG = {
    "db_url": os.getenv("DATABASE_URL", "postgresql://aml_user:aml_password@postgres:5432/aml_db"),
    "kafka_bootstrap": os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"),
    "topic": "aml_stream",
    "batch_size": 100,
    "rate_limit_ms": 10,  # Milliseconds between messages
    "csv_fallback": "data/raw/HI-Medium_Trans.csv",
}


def create_producer() -> KafkaProducer:
    """Create and configure Kafka producer."""
    print(f"🔌 Connecting to Kafka at {CONFIG['kafka_bootstrap']}...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=[CONFIG['kafka_bootstrap']],
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=3,
            retry_backoff_ms=500,
        )
        print("   ✅ Kafka producer connected")
        return producer
    except KafkaError as e:
        print(f"   ❌ Kafka connection failed: {e}")
        raise


def load_from_database() -> pd.DataFrame:
    """Load transactions from PostgreSQL."""
    print(f"\n💾 Loading transactions from database...")
    
    try:
        engine = create_engine(CONFIG['db_url'])
        
        query = """
            SELECT 
                id, timestamp, from_bank, source_account, 
                to_bank, destination_account, amount_received, 
                receiving_currency, amount_paid, payment_currency,
                payment_format, is_laundering, high_risk_outlier
            FROM transactions
            ORDER BY timestamp
        """
        
        df = pd.read_sql(query, engine)
        print(f"   Loaded {len(df):,} transactions from database")
        return df
        
    except Exception as e:
        print(f"   ⚠️  Database unavailable: {e}")
        return None


def load_from_csv() -> pd.DataFrame:
    """Load transactions from CSV as fallback."""
    print(f"\n📂 Loading from CSV: {CONFIG['csv_fallback']}...")
    
    try:
        df = pd.read_csv(CONFIG['csv_fallback'], low_memory=False)
        
        # Fix duplicate Account columns
        columns = list(df.columns)
        new_columns = []
        account_count = 0
        
        for col in columns:
            if col == "Account":
                if account_count == 0:
                    new_columns.append("source_account")
                else:
                    new_columns.append("destination_account")
                account_count += 1
            else:
                new_columns.append(col.lower().replace(" ", "_"))
        
        df.columns = new_columns
        print(f"   Loaded {len(df):,} transactions from CSV")
        return df
        
    except FileNotFoundError:
        print(f"   ❌ CSV file not found")
        return None


def on_send_success(record_metadata):
    """Callback for successful message delivery."""
    pass  # Silent success


def on_send_error(excp):
    """Callback for failed message delivery."""
    print(f"   ❌ Message delivery failed: {excp}")


def stream_transactions(producer: KafkaProducer, df: pd.DataFrame) -> None:
    """Stream transactions to Kafka topic."""
    print(f"\n📡 Streaming to Kafka topic '{CONFIG['topic']}'...")
    
    total = len(df)
    sent = 0
    start_time = datetime.now()
    
    for idx, row in df.iterrows():
        # Create transaction event
        event = {
            "event_type": "transaction",
            "event_time": datetime.now().isoformat(),
            "data": {
                "id": int(row.get('id', idx)),
                "timestamp": str(row.get('timestamp', '')),
                "from_bank": str(row.get('from_bank', '')),
                "source_account": str(row.get('source_account', '')),
                "to_bank": str(row.get('to_bank', '')),
                "destination_account": str(row.get('destination_account', '')),
                "amount_received": float(row.get('amount_received', 0) or 0),
                "amount_paid": float(row.get('amount_paid', 0) or 0),
                "receiving_currency": str(row.get('receiving_currency', 'USD')),
                "payment_currency": str(row.get('payment_currency', 'USD')),
                "payment_format": str(row.get('payment_format', '')),
                "is_laundering": int(row.get('is_laundering', 0) or 0),
                "high_risk_outlier": bool(row.get('high_risk_outlier', False)),
            }
        }
        
        # Use source_account as partition key for ordering
        key = event['data']['source_account']
        
        # Send asynchronously
        future = producer.send(
            CONFIG['topic'],
            key=key,
            value=event
        )
        future.add_callback(on_send_success)
        future.add_errback(on_send_error)
        
        sent += 1
        
        # Progress update every 1000 messages
        if sent % 1000 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = sent / elapsed if elapsed > 0 else 0
            print(f"   📦 Sent {sent:,}/{total:,} ({sent/total*100:.1f}%) - {rate:.0f} msg/sec")
        
        # Rate limiting
        if CONFIG['rate_limit_ms'] > 0:
            time.sleep(CONFIG['rate_limit_ms'] / 1000)
    
    # Flush remaining messages
    producer.flush()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    rate = sent / elapsed if elapsed > 0 else 0
    
    print(f"\n   ✅ Streaming complete!")
    print(f"   Total messages: {sent:,}")
    print(f"   Total time: {elapsed:.1f}s")
    print(f"   Average rate: {rate:.0f} msg/sec")


def main():
    """Main execution pipeline."""
    print("=" * 60)
    print("🏦 AML Transaction Intelligence - Kafka Producer")
    print("=" * 60)
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Load data (try database first, then CSV)
    df = load_from_database()
    if df is None or len(df) == 0:
        df = load_from_csv()
    
    if df is None or len(df) == 0:
        print("\n❌ No data available to stream")
        sys.exit(1)
    
    # Create Kafka producer
    try:
        producer = create_producer()
    except Exception as e:
        print(f"\n❌ Failed to connect to Kafka: {e}")
        print("   Make sure Docker containers are running: docker compose up -d")
        sys.exit(1)
    
    # Stream transactions
    try:
        stream_transactions(producer, df)
    except KeyboardInterrupt:
        print("\n\n⚠️  Streaming interrupted by user")
    finally:
        producer.close()
        print("\n🔌 Producer connection closed")


if __name__ == "__main__":
    main()
