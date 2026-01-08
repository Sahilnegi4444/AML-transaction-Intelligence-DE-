"""
AML Transaction Intelligence - Complete Pipeline
=================================================
Unified PySpark pipeline for:
1. Data cleaning and outlier detection
2. Anomaly detection with alert generation
3. Store transactions AND alerts in PostgreSQL

Uses optimal batch processing with PySpark.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, count, sum as spark_sum, avg, 
    percentile_approx, to_timestamp, window, 
    min as spark_min, max as spark_max, round as spark_round,
    current_timestamp
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType

# Configuration
CONFIG = {
    "csv_path": os.getenv("CSV_PATH", "data/raw/HI-Medium_Trans.csv"),
    "db_url": os.getenv("DATABASE_URL", "jdbc:postgresql://postgres:5432/aml_db"),
    "db_user": os.getenv("POSTGRES_USER", "aml_user"),
    "db_password": os.getenv("POSTGRES_PASSWORD", "aml_password"),
    "sample_size": int(os.getenv("SAMPLE_SIZE", "100000")),
    # Anomaly detection thresholds
    "min_transaction_count": 2,  # count > 2
    "min_total_amount": 10000,   # OR total > 10000
    "window_duration": "10 minutes",
}

# Define schema with explicit column names (no duplicates)
SCHEMA = StructType([
    StructField("timestamp", StringType(), True),
    StructField("from_bank", StringType(), True),
    StructField("source_account", StringType(), True),
    StructField("to_bank", StringType(), True),
    StructField("destination_account", StringType(), True),
    StructField("amount_received", DoubleType(), True),
    StructField("receiving_currency", StringType(), True),
    StructField("amount_paid", DoubleType(), True),
    StructField("payment_currency", StringType(), True),
    StructField("payment_format", StringType(), True),
    StructField("is_laundering", IntegerType(), True),
])


def create_spark_session() -> SparkSession:
    """Create Spark session with PostgreSQL JDBC."""
    print("\n🔧 Initializing Spark session...")
    
    spark = SparkSession.builder \
        .appName("AML-FullPipeline") \
        .config("spark.jars.packages", "org.postgresql:postgresql:42.6.0") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.shuffle.partitions", "8") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print("   ✅ Spark session created")
    return spark


def load_and_clean_data(spark: SparkSession):
    """Load CSV with explicit schema and perform data cleaning."""
    print(f"\n📂 Loading data from {CONFIG['csv_path']}...")
    
    # Load CSV with explicit schema (avoids duplicate column issues)
    df = spark.read \
        .option("header", "true") \
        .schema(SCHEMA) \
        .csv(CONFIG['csv_path'])
    
    total_count = df.count()
    print(f"   Total rows in file: {total_count:,}")
    print(f"   Columns: {df.columns}")
    
    # Sample for demo
    if CONFIG['sample_size'] and total_count > CONFIG['sample_size']:
        df = df.limit(CONFIG['sample_size'])
        print(f"   Using sample of {CONFIG['sample_size']:,} rows")
    
    # Detect outliers (99th percentile)
    print("\n🔍 Detecting outliers...")
    p99 = df.select(percentile_approx(col("amount_paid"), 0.99)).collect()[0][0]
    print(f"   99th percentile threshold: ${p99:,.2f}")
    
    df = df.withColumn(
        "high_risk_outlier",
        when(col("amount_paid") > p99, True).otherwise(False)
    )
    
    outlier_count = df.filter(col("high_risk_outlier") == True).count()
    print(f"   ✅ Flagged {outlier_count:,} high-risk outliers")
    
    # Analyze class imbalance
    print("\n⚖️  Class imbalance analysis...")
    total = df.count()
    illicit = df.filter(col("is_laundering") == 1).count()
    licit = total - illicit
    ratio = licit / max(illicit, 1)
    print(f"   Licit: {licit:,} | Illicit: {illicit:,} | Ratio: {ratio:.1f}:1")
    
    return df


def detect_anomalies(df):
    """
    Detect suspicious patterns using windowed aggregation.
    Rule: (count > 2) OR (total_amount > 10000)
    """
    print(f"\n🚨 Detecting anomalies...")
    print(f"   Rule: (count > {CONFIG['min_transaction_count']}) OR (total > ${CONFIG['min_total_amount']:,})")
    print(f"   Window: {CONFIG['window_duration']}")
    
    # Ensure timestamp is proper type
    df = df.withColumn("event_time", to_timestamp(col("timestamp"), "yyyy/MM/dd HH:mm"))
    
    # Window aggregation by source account
    windowed = df.groupBy(
        col("source_account"),
        window(col("event_time"), CONFIG["window_duration"])
    ).agg(
        count("*").alias("transaction_count"),
        spark_round(spark_sum("amount_paid"), 2).alias("total_amount"),
        spark_round(avg("amount_paid"), 2).alias("avg_amount"),
        spark_min("event_time").alias("window_start"),
        spark_max("event_time").alias("window_end"),
        spark_sum(when(col("is_laundering") == 1, 1).otherwise(0)).alias("known_illicit")
    )
    
    # Filter for anomalies: AND condition (both must be true)
    alerts = windowed.filter(
        (col("transaction_count") > CONFIG["min_transaction_count"]) & 
        (col("total_amount") > CONFIG["min_total_amount"])
    )
    
    # Add alert metadata
    alerts = alerts.select(
        lit("SUSPICIOUS_PATTERN").alias("alert_type"),
        col("source_account"),
        col("transaction_count"),
        col("total_amount"),
        col("avg_amount"),
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        # Risk score based on severity
        when(
            (col("transaction_count") > CONFIG["min_transaction_count"]) & 
            (col("total_amount") > CONFIG["min_total_amount"]),
            lit(0.9)  # Both conditions: HIGH risk
        ).when(
            col("total_amount") > CONFIG["min_total_amount"] * 2,
            lit(0.8)
        ).when(
            col("transaction_count") > CONFIG["min_transaction_count"] * 2,
            lit(0.7)
        ).otherwise(lit(0.5)).alias("risk_score"),
        lit("NEW").alias("status"),
        current_timestamp().alias("created_at")
    )
    
    alert_count = alerts.count()
    print(f"   ✅ Detected {alert_count:,} suspicious patterns")
    
    return alerts


def save_to_postgres(df, table_name: str, mode: str = "overwrite"):
    """Save DataFrame to PostgreSQL."""
    print(f"\n💾 Saving to PostgreSQL table '{table_name}'...")
    
    df.write \
        .format("jdbc") \
        .option("url", CONFIG["db_url"]) \
        .option("dbtable", table_name) \
        .option("user", CONFIG["db_user"]) \
        .option("password", CONFIG["db_password"]) \
        .option("driver", "org.postgresql.Driver") \
        .mode(mode) \
        .save()
    
    count = df.count()
    print(f"   ✅ Saved {count:,} rows to '{table_name}'")
    return count


def main():
    """Run the complete pipeline."""
    print("=" * 70)
    print("🏦 AML Transaction Intelligence - Complete Pipeline")
    print("=" * 70)
    
    start_time = datetime.now()
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    spark = create_spark_session()
    
    try:
        # ========================================
        # STEP 1: Load and Clean Data
        # ========================================
        df = load_and_clean_data(spark)
        
        # ========================================
        # STEP 2: Detect Anomalies
        # ========================================
        alerts_df = detect_anomalies(df)
        
        # ========================================
        # STEP 3: Save Transactions to PostgreSQL
        # ========================================
        # Prepare transactions for DB
        transactions = df.withColumn(
            "timestamp",
            to_timestamp(col("timestamp"), "yyyy/MM/dd HH:mm")
        )
        
        tx_count = save_to_postgres(transactions, "transactions", "overwrite")
        
        # ========================================
        # STEP 4: Save Alerts to PostgreSQL
        # ========================================
        if alerts_df.count() > 0:
            alert_count = save_to_postgres(alerts_df, "alerts", "overwrite")
        else:
            alert_count = 0
            print("\n   ℹ️ No alerts to save")
        
        # ========================================
        # SUMMARY
        # ========================================
        elapsed = datetime.now() - start_time
        outliers = df.filter(col("high_risk_outlier") == True).count()
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETE!")
        print("=" * 70)
        print(f"""
   ⏱️  Total time: {elapsed.total_seconds():.1f} seconds
   
   📊 TRANSACTIONS:
      - Processed: {tx_count:,}
      - High-risk outliers: {outliers:,}
   
   🚨 ALERTS:
      - Suspicious patterns: {alert_count:,}
      - Detection rule: (count > 2) AND (total > $10,000)
   
   💾 DATABASE:
      - transactions table: {tx_count:,} rows
      - alerts table: {alert_count:,} rows
        """)
        print("=" * 70)
        
    finally:
        spark.stop()
        print("\n🔌 Spark session closed")


if __name__ == "__main__":
    main()
