# Power BI Desktop - PostgreSQL Connection Guide

This guide explains how to connect Power BI Desktop to the local AML Transaction Intelligence PostgreSQL database.

## Prerequisites

1. **Power BI Desktop** installed (Windows only)
2. **Docker containers running**: `docker compose up -d`
3. **PostgreSQL connector** (included with Power BI Desktop)

## Connection Details

| Parameter | Value |
|-----------|-------|
| **Server** | `localhost` |
| **Port** | `5432` |
| **Database** | `aml_db` |
| **Username** | `aml_user` |
| **Password** | `aml_password` |

## Step-by-Step Instructions

### 1. Open Power BI Desktop

Launch Power BI Desktop from your Windows Start menu.

### 2. Get Data

1. Click **Home** → **Get Data** → **More...**
2. Search for **PostgreSQL**
3. Select **PostgreSQL database** and click **Connect**

### 3. Configure Connection

Enter the following in the connection dialog:

- **Server**: `localhost:5432`
- **Database**: `aml_db`
- **Data Connectivity mode**: `Import` (recommended) or `DirectQuery`

Click **OK**.

### 4. Enter Credentials

1. Select **Database** tab (not Windows)
2. Enter:
   - **User name**: `aml_user`
   - **Password**: `aml_password`
3. Click **Connect**

### 5. Select Tables

In the Navigator, select the tables you want to visualize:

- ☑️ `alerts` - Suspicious activity alerts
- ☑️ `transactions` - Cleaned transaction data
- ☑️ `regulatory_docs` - Embedded regulations (optional)

Click **Load** or **Transform Data** (for data modeling).

## Recommended Visualizations

### Alerts Dashboard

1. **Alert Timeline**
   - Chart type: Line chart
   - X-axis: `created_at` (by day)
   - Values: Count of `id`

2. **Risk Score Distribution**
   - Chart type: Donut chart
   - Legend: `risk_score` (binned)
   - Values: Count

3. **Top Accounts by Alert Count**
   - Chart type: Bar chart
   - Axis: `source_account`
   - Values: Count of `id`
   - Top N filter: 10

4. **Alert Status Overview**
   - Chart type: Card or KPI
   - Values: Count by `status`

### Transaction Analytics

1. **Transaction Volume Over Time**
   - Chart type: Area chart
   - X-axis: `timestamp` (by day)
   - Values: Sum of `amount_paid`

2. **High-Risk Outliers**
   - Chart type: Table
   - Columns: `timestamp`, `source_account`, `amount_paid`, `high_risk_outlier`
   - Filter: `high_risk_outlier` = TRUE

3. **Laundering Indicator Distribution**
   - Chart type: Pie chart
   - Legend: `is_laundering`
   - Values: Count

## Refresh Settings

For real-time monitoring:

1. Go to **Home** → **Transform data** → **Data source settings**
2. Enable **Scheduled refresh** (requires Power BI Gateway for local sources)

For manual refresh: Click **Refresh** button in the Home ribbon.

## Troubleshooting

### Cannot connect to server

1. Verify Docker is running: `docker compose ps`
2. Check PostgreSQL port: `netstat -an | findstr 5432`
3. Verify no firewall blocking port 5432

### Authentication failed

1. Verify credentials match `docker-compose.yaml`
2. Try connecting via psql first:
   ```powershell
   docker compose exec postgres psql -U aml_user -d aml_db
   ```

### Slow performance

1. Switch from DirectQuery to Import mode
2. Add date range filters to limit data
3. Create aggregated views in PostgreSQL

## Sample DAX Measures

```dax
// Total Alerts
Total Alerts = COUNTROWS(alerts)

// High Risk Alert Rate
High Risk Rate = 
DIVIDE(
    CALCULATE(COUNTROWS(alerts), alerts[risk_score] > 0.7),
    COUNTROWS(alerts)
)

// Average Transaction Amount
Avg Transaction = AVERAGE(transactions[amount_paid])

// Suspicious Transaction Value
Suspicious Value = 
CALCULATE(
    SUM(transactions[amount_paid]),
    transactions[is_laundering] = 1
)
```

---

*Last Updated: 2024-01-01*
