"""
AML Transaction Intelligence - PySpark Anomaly Detection
==========================================================
Batch anomaly detection using PySpark.

Features:
- Batch processing of transactions from PostgreSQL
- 10-minute window aggregation per account
- Anomaly detection: (count > 2) AND (total_amount > 10000)
- Dynamic risk scoring based on multiple factors
- Writes detected alerts to PostgreSQL alerts table
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, min as spark_min, 
    max as spark_max, window, to_timestamp, lit, current_timestamp,
    when, round as spark_round, monotonically_increasing_id, row_number
)
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    IntegerType, BooleanType, TimestampType
)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration
CONFIG = {
    "db_url": os.getenv("DATABASE_URL", "jdbc:postgresql://postgres:5432/aml_db"),
    "db_user": os.getenv("POSTGRES_USER", "aml_user"),
    "db_password": os.getenv("POSTGRES_PASSWORD", "aml_password"),
    "window_duration": "1 hour",
    "output_dir": "output/plots",
    # Detection thresholds - AND condition
    "min_transaction_count": 2,  # count > 2
    "min_total_amount": 10000,   # AND total > 10000
}


def create_spark_session() -> SparkSession:
    """Create and configure Spark session."""
    print("\n🔧 Initializing Spark session for anomaly detection...")
    
    spark = SparkSession.builder \
        .appName("AML-AnomalyDetection") \
        .config("spark.jars.packages", "org.postgresql:postgresql:42.6.0") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print("   ✅ Spark session created")
    
    return spark


def load_transactions(spark: SparkSession) -> "DataFrame":
    """Load transactions from PostgreSQL."""
    print("\n📂 Loading transactions from PostgreSQL...")
    
    df = spark.read \
        .format("jdbc") \
        .option("url", CONFIG["db_url"]) \
        .option("dbtable", "transactions") \
        .option("user", CONFIG["db_user"]) \
        .option("password", CONFIG["db_password"]) \
        .option("driver", "org.postgresql.Driver") \
        .load()
    
    count = df.count()
    print(f"   Loaded {count:,} transactions")
    
    return df


def calculate_dynamic_risk_score(df):
    """
    Calculate dynamic risk score based on multiple factors:
    - Transaction velocity (count relative to threshold)
    - Amount severity (total relative to threshold)
    - Known illicit transaction ratio
    
    Returns score between 0.3 and 1.0
    """
    # Normalize transaction count: score increases with more transactions
    # Base: 3 txns = 0.1, 10+ txns = 0.3
    count_score = when(
        col("transaction_count") >= 10, lit(0.30)
    ).when(
        col("transaction_count") >= 7, lit(0.25)
    ).when(
        col("transaction_count") >= 5, lit(0.20)
    ).when(
        col("transaction_count") >= 4, lit(0.15)
    ).otherwise(lit(0.10))
    
    # Normalize amount: score increases with higher amounts
    # Base: $10K = 0.1, $100K+ = 0.4
    amount_score = when(
        col("total_amount") >= 100000, lit(0.40)
    ).when(
        col("total_amount") >= 50000, lit(0.30)
    ).when(
        col("total_amount") >= 25000, lit(0.20)
    ).when(
        col("total_amount") >= 15000, lit(0.15)
    ).otherwise(lit(0.10))
    
    # Known illicit transactions boost
    illicit_score = when(
        col("known_illicit_count") >= 2, lit(0.30)
    ).when(
        col("known_illicit_count") >= 1, lit(0.20)
    ).otherwise(lit(0.0))
    
    # Combine scores: base 0.2 + count + amount + illicit
    # Max possible: 0.2 + 0.3 + 0.4 + 0.3 = 1.0
    # Min possible: 0.2 + 0.1 + 0.1 + 0.0 = 0.4
    total_score = lit(0.20) + count_score + amount_score + illicit_score
    
    # Clamp between 0.3 and 1.0
    return when(total_score > 1.0, lit(1.0)).when(total_score < 0.3, lit(0.3)).otherwise(total_score)


def detect_anomalies(df) -> "DataFrame":
    """
    Detect anomalous transaction patterns using windowed aggregation.
    
    Alert Condition: (transaction_count > 2) AND (total_amount > 10000)
    """
    print("\n🔍 Detecting anomalies...")
    print(f"   Window: {CONFIG['window_duration']}")
    print(f"   Condition: (count > {CONFIG['min_transaction_count']}) AND (total > ${CONFIG['min_total_amount']:,})")
    
    # Ensure timestamp is proper type
    df = df.withColumn("event_time", to_timestamp(col("timestamp")))
    
    # Window aggregation by source account
    windowed_df = df.groupBy(
        col("source_account"),
        window(col("event_time"), CONFIG["window_duration"])
    ).agg(
        count("*").alias("transaction_count"),
        spark_round(spark_sum("amount_paid"), 2).alias("total_amount"),
        spark_round(avg("amount_paid"), 2).alias("avg_amount"),
        spark_min("event_time").alias("window_start"),
        spark_max("event_time").alias("window_end"),
        spark_sum(when(col("is_laundering") == 1, 1).otherwise(0)).alias("known_illicit_count")
    )
    
    # Apply detection rule: AND condition
    alerts_df = windowed_df.filter(
        (col("transaction_count") > CONFIG["min_transaction_count"]) & 
        (col("total_amount") > CONFIG["min_total_amount"])
    )
    
    # Calculate dynamic risk score
    risk_score_expr = calculate_dynamic_risk_score(alerts_df)
    
    # Add metadata with dynamic risk score
    alerts_df = alerts_df.select(
        lit("SUSPICIOUS_PATTERN").alias("alert_type"),
        col("source_account"),
        col("transaction_count"),
        col("total_amount"),
        col("avg_amount"),
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end"),
        spark_round(risk_score_expr, 2).alias("risk_score"),
        lit("NEW").alias("status"),
        current_timestamp().alias("created_at"),
        col("known_illicit_count")
    )
    
    # Order by risk score descending, then by total amount
    alerts_df = alerts_df.orderBy(col("risk_score").desc(), col("total_amount").desc())
    
    # Add ascending alert ID (1, 2, 3, ...)
    window_spec = Window.orderBy(col("risk_score").desc(), col("total_amount").desc())
    alerts_df = alerts_df.withColumn("alert_id", row_number().over(window_spec))
    
    alert_count = alerts_df.count()
    print(f"   ✅ Detected {alert_count:,} suspicious patterns")
    
    # Show risk distribution
    if alert_count > 0:
        risk_stats = alerts_df.agg(
            spark_round(avg("risk_score"), 2).alias("avg_risk"),
            spark_round(spark_min("risk_score"), 2).alias("min_risk"),
            spark_round(spark_max("risk_score"), 2).alias("max_risk")
        ).collect()[0]
        print(f"   Risk scores: min={risk_stats['min_risk']}, avg={risk_stats['avg_risk']}, max={risk_stats['max_risk']}")
    
    return alerts_df


def save_alerts(alerts_df, spark: SparkSession):
    """Save detected alerts to PostgreSQL."""
    print("\n💾 Saving alerts to PostgreSQL...")
    
    # Select columns for database (exclude alert_id, let PostgreSQL generate serial ID)
    alerts_df = alerts_df.select(
        "alert_type",
        "source_account",
        "transaction_count",
        "total_amount",
        "avg_amount",
        "window_start",
        "window_end",
        "risk_score",
        "status",
        "created_at"
    )
    
    # Write alerts to database (append mode)
    alerts_df.write \
        .format("jdbc") \
        .option("url", CONFIG["db_url"]) \
        .option("dbtable", "alerts") \
        .option("user", CONFIG["db_user"]) \
        .option("password", CONFIG["db_password"]) \
        .option("driver", "org.postgresql.Driver") \
        .mode("append") \
        .save()
    
    count = alerts_df.count()
    print(f"   ✅ Saved {count:,} alerts to database")
    
    return count


def create_detection_visualizations(alerts_df, output_dir: str):
    """Create visualizations for detection results."""
    print(f"\n📊 Generating detection visualizations to {output_dir}/...")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert to Pandas for visualization
    alerts_pd = alerts_df.toPandas()
    
    if len(alerts_pd) == 0:
        print("   ⚠️ No alerts to visualize")
        return
    
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # =========================================
    # Plot 1: Alert Distribution by Risk Score
    # =========================================
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Risk score distribution
    ax1 = axes[0]
    risk_bins = [0, 0.5, 0.7, 0.85, 1.01]
    risk_labels = ['Low (0.3-0.5)', 'Medium (0.5-0.7)', 'High (0.7-0.85)', 'Critical (0.85-1.0)']
    alerts_pd['risk_category'] = pd.cut(
        alerts_pd['risk_score'], 
        bins=risk_bins, 
        labels=risk_labels,
        include_lowest=True
    )
    
    risk_counts = alerts_pd['risk_category'].value_counts().sort_index()
    colors = ['#3498db', '#f39c12', '#e74c3c', '#8e44ad']
    
    ax1.bar(range(len(risk_counts)), risk_counts.values, color=colors[:len(risk_counts)])
    ax1.set_xticks(range(len(risk_counts)))
    ax1.set_xticklabels([str(x) for x in risk_counts.index], rotation=15, ha='right')
    ax1.set_title('Alerts by Risk Category', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Risk Category', fontsize=12)
    ax1.set_ylabel('Number of Alerts', fontsize=12)
    
    for i, val in enumerate(risk_counts.values):
        ax1.annotate(f'{val:,}', xy=(i, val), ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Transaction count vs Total amount scatter
    ax2 = axes[1]
    scatter = ax2.scatter(
        alerts_pd['transaction_count'], 
        alerts_pd['total_amount'],
        c=alerts_pd['risk_score'],
        cmap='RdYlGn_r',
        alpha=0.6,
        s=50
    )
    ax2.axhline(y=CONFIG['min_total_amount'], color='red', linestyle='--', label=f'Amount Threshold: ${CONFIG["min_total_amount"]:,}')
    ax2.axvline(x=CONFIG['min_transaction_count'], color='blue', linestyle='--', label=f'Count Threshold: {CONFIG["min_transaction_count"]}')
    ax2.set_title('Alert Pattern Analysis\n(count > 2 AND total > $10,000)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Transaction Count', fontsize=12)
    ax2.set_ylabel('Total Amount ($)', fontsize=12)
    ax2.legend(loc='upper right')
    plt.colorbar(scatter, ax=ax2, label='Risk Score')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/alert_distribution.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ Saved: alert_distribution.png")
    
    # =========================================
    # Plot 2: Top Suspicious Accounts
    # =========================================
    fig, ax = plt.subplots(figsize=(12, 6))
    
    top_accounts = alerts_pd.nlargest(10, 'total_amount')
    
    colors = plt.cm.RdYlGn_r(top_accounts['risk_score'])
    bars = ax.barh(
        top_accounts['source_account'].astype(str), 
        top_accounts['total_amount'],
        color=colors
    )
    
    ax.set_title('Top 10 Suspicious Accounts by Total Amount', fontsize=14, fontweight='bold')
    ax.set_xlabel('Total Amount ($)', fontsize=12)
    ax.set_ylabel('Account ID', fontsize=12)
    
    # Add value labels
    for bar, val in zip(bars, top_accounts['total_amount']):
        ax.annotate(f'${val:,.0f}', xy=(val, bar.get_y() + bar.get_height()/2),
                    xytext=(5, 0), textcoords='offset points',
                    ha='left', va='center', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/top_suspicious_accounts.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ Saved: top_suspicious_accounts.png")


def print_summary(alerts_df, total_transactions: int):
    """Print detection summary."""
    print("\n" + "=" * 60)
    print("📋 DETECTION SUMMARY")
    print("=" * 60)
    
    total_alerts = alerts_df.count()
    
    if total_alerts == 0:
        print("   No suspicious patterns detected")
        return
    
    # Aggregate statistics
    stats = alerts_df.agg(
        count("*").alias("total_alerts"),
        spark_sum("transaction_count").alias("total_transactions"),
        spark_round(spark_sum("total_amount"), 2).alias("total_flagged_amount"),
        spark_round(avg("risk_score"), 2).alias("avg_risk_score"),
        spark_round(spark_min("risk_score"), 2).alias("min_risk"),
        spark_round(spark_max("risk_score"), 2).alias("max_risk"),
        spark_sum("known_illicit_count").alias("known_illicit")
    ).collect()[0]
    
    detection_rate = (stats['total_alerts'] / total_transactions) * 100
    
    print(f"""
   Total Alerts Generated: {stats['total_alerts']:,}
   Total Transactions Analyzed: {total_transactions:,}
   Detection Rate: {detection_rate:.2f}%
   
   Total Flagged Amount: ${stats['total_flagged_amount']:,.2f}
   
   Risk Score Distribution:
      Min: {stats['min_risk']:.2f}
      Avg: {stats['avg_risk_score']:.2f}
      Max: {stats['max_risk']:.2f}
   
   Known Illicit in Flags: {int(stats['known_illicit']):,}
   
   Detection Rule: (count > {CONFIG['min_transaction_count']}) AND (total > ${CONFIG['min_total_amount']:,})
    """)
    
    # Show sample alerts
    print("   Top 5 Highest Risk Alerts:")
    print("   " + "-" * 50)
    
    top_alerts = alerts_df.orderBy(col("risk_score").desc(), col("total_amount").desc()).limit(5).collect()
    for i, alert in enumerate(top_alerts, 1):
        print(f"   #{i} Account: {alert['source_account']}")
        print(f"      Txns: {alert['transaction_count']}, Total: ${alert['total_amount']:,.2f}, Risk: {alert['risk_score']:.2f}")
        print()


def main():
    """Main execution pipeline."""
    print("=" * 60)
    print("🏦 AML Transaction Intelligence - PySpark Anomaly Detection")
    print("=" * 60)
    
    start_time = datetime.now()
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # Load transactions
        df = load_transactions(spark)
        total_transactions = df.count()
        
        if total_transactions == 0:
            print("\n⚠️ No transactions found. Run clean_and_store.py first.")
            return
        
        # Detect anomalies
        alerts_df = detect_anomalies(df)
        
        # Save alerts to database
        if alerts_df.count() > 0:
            try:
                save_alerts(alerts_df, spark)
            except Exception as e:
                print(f"   ⚠️ Could not save to database: {e}")
            
            # Create visualizations
            try:
                import pandas as pd
                create_detection_visualizations(alerts_df, CONFIG['output_dir'])
            except Exception as e:
                print(f"   ⚠️ Visualization generation skipped: {e}")
        
        # Print summary
        print_summary(alerts_df, total_transactions)
        
        elapsed = datetime.now() - start_time
        print(f"\n⏱️  Total execution time: {elapsed.total_seconds():.1f} seconds")
        print("=" * 60)
        
    finally:
        spark.stop()
        print("\n🔌 Spark session closed")


if __name__ == "__main__":
    main()
