"""
AML Transaction Intelligence - PySpark Anomaly Detection
==========================================================
Real-time and batch anomaly detection using PySpark.

Features:
- Batch processing of transactions from PostgreSQL
- 10-minute window aggregation per account
- Anomaly detection: (count > 2) OR (total_amount > 10000)
- Writes detected alerts to PostgreSQL alerts table
- Generates detection statistics and visualizations
"""

import os
import sys
from pathlib import Path
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, min as spark_min, 
    max as spark_max, window, to_timestamp, lit, current_timestamp,
    when, round as spark_round
)
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
    "window_duration": "10 minutes",
    "output_dir": "output/plots",
    # Detection thresholds - OR condition
    "min_transaction_count": 2,  # count > 2
    "min_total_amount": 10000,   # OR total > 10000
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


def detect_anomalies(df) -> "DataFrame":
    """
    Detect anomalous transaction patterns using windowed aggregation.
    
    Alert Condition: (transaction_count > 2) OR (total_amount > 10000)
    This catches:
    - Structuring: Many small transactions (count > 2)
    - Large transfers: Single or few large transactions (total > 10000)
    """
    print("\n🔍 Detecting anomalies...")
    print(f"   Window: {CONFIG['window_duration']}")
    print(f"   Condition: (count > {CONFIG['min_transaction_count']}) OR (total > ${CONFIG['min_total_amount']:,})")
    
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
    
    # Apply detection rule: OR condition
    alerts_df = windowed_df.filter(
        (col("transaction_count") > CONFIG["min_transaction_count"]) | 
        (col("total_amount") > CONFIG["min_total_amount"])
    )
    
    # Add metadata
    alerts_df = alerts_df.select(
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
            lit(0.8)  # Very large amount
        ).when(
            col("transaction_count") > CONFIG["min_transaction_count"] * 2,
            lit(0.7)  # Many transactions
        ).otherwise(lit(0.5)).alias("risk_score"),
        lit("NEW").alias("status"),
        current_timestamp().alias("created_at"),
        col("known_illicit_count")
    )
    
    alert_count = alerts_df.count()
    print(f"   ✅ Detected {alert_count:,} suspicious patterns")
    
    return alerts_df


def save_alerts(alerts_df, spark: SparkSession):
    """Save detected alerts to PostgreSQL."""
    print("\n💾 Saving alerts to PostgreSQL...")
    
    # Write alerts to database
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
    risk_bins = [0, 0.5, 0.7, 0.9, 1.0]
    risk_labels = ['Low', 'Medium', 'High', 'Critical']
    alerts_pd['risk_category'] = pd.cut(
        alerts_pd['risk_score'], 
        bins=risk_bins, 
        labels=risk_labels,
        include_lowest=True
    )
    
    risk_counts = alerts_pd['risk_category'].value_counts()
    colors = ['#3498db', '#f39c12', '#e74c3c', '#8e44ad']
    
    ax1.bar(risk_counts.index.astype(str), risk_counts.values, color=colors[:len(risk_counts)])
    ax1.set_title('Alerts by Risk Category', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Risk Category', fontsize=12)
    ax1.set_ylabel('Number of Alerts', fontsize=12)
    
    for i, (cat, val) in enumerate(zip(risk_counts.index, risk_counts.values)):
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
    ax2.set_title('Alert Pattern Analysis\n(count > 2 OR total > $10,000)', fontsize=14, fontweight='bold')
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


def print_summary(alerts_df):
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
        spark_sum("known_illicit_count").alias("known_illicit")
    ).collect()[0]
    
    print(f"""
   Total Alerts Generated: {stats['total_alerts']:,}
   Total Transactions Flagged: {int(stats['total_transactions']):,}
   Total Flagged Amount: ${stats['total_flagged_amount']:,.2f}
   Average Risk Score: {stats['avg_risk_score']:.2f}
   Known Illicit in Flags: {int(stats['known_illicit']):,}
   
   Detection Rule: (count > {CONFIG['min_transaction_count']}) OR (total > ${CONFIG['min_total_amount']:,})
    """)
    
    # Show sample alerts
    print("   Top 5 Highest Risk Alerts:")
    print("   " + "-" * 50)
    
    top_alerts = alerts_df.orderBy(col("risk_score").desc()).limit(5).collect()
    for alert in top_alerts:
        print(f"   Account: {alert['source_account']}")
        print(f"      Transactions: {alert['transaction_count']}, Total: ${alert['total_amount']:,.2f}, Risk: {alert['risk_score']:.2f}")
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
        
        if df.count() == 0:
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
        print_summary(alerts_df)
        
        elapsed = datetime.now() - start_time
        print(f"\n⏱️  Total execution time: {elapsed.total_seconds():.1f} seconds")
        print("=" * 60)
        
    finally:
        spark.stop()
        print("\n🔌 Spark session closed")


if __name__ == "__main__":
    main()
