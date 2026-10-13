"""Visualization module: generates publication-grade Matplotlib charts from real DuckDB query results."""
import sys
from pathlib import Path
from typing import List
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.config import config, logger

# Set clean aesthetic style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.labelweight": "semibold",
    "figure.titlesize": 14,
    "figure.titleweight": "bold",
})

def generate_monthly_revenue_chart(output_dir: Path) -> Path:
    """Chart 1: Monthly Gross Revenue & MoM Growth Rate."""
    csv_path = config.outputs_dir / "01_monthly_revenue_growth.csv"
    df = pd.read_csv(csv_path)
    
    # Filter out preliminary 2016 months and truncated Sept 2018 for cleaner operational view
    df_clean = df[(df['order_month'] >= '2017-01-01') & (df['order_month'] <= '2018-08-31')].copy()
    df_clean['revenue_millions'] = df_clean['monthly_revenue'] / 1_000_000.0

    fig, ax1 = plt.subplots(figsize=(10, 5), dpi=300)

    # Primary Bar: Revenue
    bars = ax1.bar(
        df_clean['order_month'], df_clean['revenue_millions'],
        color="#1f77b4", width=0.6, alpha=0.85, label="Monthly Revenue (R$ Millions)"
    )
    ax1.set_ylabel("Gross Revenue (R$ Millions)", color="#1f77b4")
    ax1.set_xlabel("Purchase Month")
    ax1.set_ylim(0, max(df_clean['revenue_millions']) * 1.25)
    ax1.tick_params(axis="x", rotation=45)
    ax1.tick_params(axis="y", labelcolor="#1f77b4")

    # Annotate Black Friday peak
    bf_row = df_clean[df_clean['order_month'] == '2017-11-01'].iloc[0]
    ax1.annotate(
        f"Black Friday Peak\nR$ {bf_row['monthly_revenue']:,.0f}",
        xy=('2017-11-01', bf_row['revenue_millions']),
        xytext=('2017-07-01', 1.25),
        arrowprops=dict(facecolor="#d62728", shrink=0.08, width=1.5, headwidth=6),
        fontweight="bold", color="#d62728"
    )

    # Secondary Line: MoM Growth %
    ax2 = ax1.twinx()
    ax2.plot(
        df_clean['order_month'], df_clean['mom_growth_pct'],
        color="#ff7f0e", marker="o", linewidth=2.2, label="MoM Growth (%)"
    )
    ax2.set_ylabel("MoM Growth Rate (%)", color="#ff7f0e")
    ax2.tick_params(axis="y", labelcolor="#ff7f0e")
    ax2.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    ax2.set_ylim(-35, 120)

    plt.title("Olist Marketplace: Monthly Revenue (GMV) & Month-over-Month Growth (2017–2018)", pad=15)
    fig.tight_layout()
    
    out_file = output_dir / "chart_1_monthly_revenue.png"
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    logger.info("Saved %s", out_file)
    return out_file

def generate_rolling_orders_chart(output_dir: Path) -> Path:
    """Chart 2: Daily Order Count with 7-Day Rolling Average."""
    csv_path = config.outputs_dir / "03_7day_rolling_order_count.csv"
    df = pd.read_csv(csv_path)
    df['calendar_date'] = pd.to_datetime(df['calendar_date'])
    
    # Focus on active operational window
    df_clean = df[df['calendar_date'] >= '2017-01-01'].copy()

    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    ax.scatter(
        df_clean['calendar_date'], df_clean['daily_order_count'],
        color="#aec7e8", s=10, alpha=0.6, label="Actual Daily Orders"
    )
    ax.plot(
        df_clean['calendar_date'], df_clean['rolling_7day_avg_orders'],
        color="#1f77b4", linewidth=2.5, label="7-Day Rolling Average"
    )

    # Highlight Black Friday record day
    peak_date = pd.to_datetime('2017-11-24')
    ax.annotate(
        "Black Friday Spike\n1,176 Orders",
        xy=(peak_date, 1176),
        xytext=(pd.to_datetime('2017-08-15'), 950),
        arrowprops=dict(facecolor="#d62728", shrink=0.08, width=1.5, headwidth=6),
        fontweight="bold", color="#d62728"
    )

    ax.set_ylabel("Order Count")
    ax.set_xlabel("Calendar Date")
    ax.set_title("Olist Marketplace: Daily Order Volume & 7-Day Rolling Trend (2017–2018)", pad=15)
    ax.legend(loc="upper left", frameon=True)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    fig.tight_layout()
    out_file = output_dir / "chart_2_rolling_orders.png"
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    logger.info("Saved %s", out_file)
    return out_file

def generate_delivery_delay_vs_review_chart(output_dir: Path) -> Path:
    """Chart 3: The Delivery Penalty Cliff: Review Scores vs Delay Buckets."""
    csv_path = config.outputs_dir / "05_delivery_delay_vs_review.csv"
    df = pd.read_csv(csv_path)

    # Clean bucket names for clean display
    bucket_labels = [
        ">7d Early", "1-7d Early", "On Estimated\nDate", "1-7d Late", ">7d Late"
    ]
    
    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=300)

    # Bar chart for Average Review Score
    bar_colors = ["#2ca02c", "#2ca02c", "#1f77b4", "#ff7f0e", "#d62728"]
    bars = ax1.bar(
        bucket_labels, df['avg_review_score'],
        color=bar_colors, width=0.55, alpha=0.85, label="Avg Review Score (1-5)"
    )
    ax1.set_ylabel("Average Review Score (1 to 5)", fontweight="bold")
    ax1.set_ylim(0, 5.2)

    for bar, score in zip(bars, df['avg_review_score']):
        ax1.text(
            bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
            f"{score:.2f}/5", ha="center", va="bottom", fontweight="bold"
        )

    # Twin axis for 1-star percentage
    ax2 = ax1.twinx()
    ax2.plot(
        bucket_labels, df['pct_1_star_reviews'],
        color="#8c1515", marker="s", linewidth=2.5, markersize=8, label="% 1-Star Ratings"
    )
    ax2.set_ylabel("% Receiving 1-Star Review (Worst Rating)", color="#8c1515", fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="#8c1515")
    ax2.set_ylim(0, 80)

    for idx, (lbl, pct) in enumerate(zip(bucket_labels, df['pct_1_star_reviews'])):
        ax2.text(idx, pct + 3.0, f"{pct:.1f}%", ha="center", color="#8c1515", fontweight="bold")

    plt.title("The Delivery Penalty Cliff: Customer Review Scores Collapse with Delivery Lateness", pad=15)
    fig.tight_layout()

    out_file = output_dir / "chart_3_delivery_delay_vs_review.png"
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    logger.info("Saved %s", out_file)
    return out_file

def generate_top_categories_by_state_chart(output_dir: Path) -> Path:
    """Chart 4: Category Dominance across Top 5 Brazilian Consumer States."""
    csv_path = config.outputs_dir / "02_top3_categories_by_state.csv"
    df = pd.read_csv(csv_path)

    top_states = ["SP", "RJ", "MG", "RS", "PR"]
    df_filtered = df[df['customer_state'].isin(top_states)].copy()

    # Pivot for clustered bar chart
    pivot_df = df_filtered.pivot(index="customer_state", columns="category_rank", values="category_name")
    rev_pivot = df_filtered.pivot(index="customer_state", columns="category_rank", values="total_revenue") / 1_000.0

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    # Plot top 3 ranks
    bar_width = 0.25
    x = range(len(top_states))
    
    rects1 = ax.bar([i - bar_width for i in x], rev_pivot[1], width=bar_width, label="Rank 1 Category", color="#1f77b4")
    rects2 = ax.bar(x, rev_pivot[2], width=bar_width, label="Rank 2 Category", color="#aec7e8")
    rects3 = ax.bar([i + bar_width for i in x], rev_pivot[3], width=bar_width, label="Rank 3 Category", color="#c7c7c7")

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"State: {s}" for s in top_states], fontweight="bold")
    ax.set_ylabel("Category GMV (R$ Thousands)")
    ax.set_title("Top 3 Product Categories by Revenue across Top 5 Consumer States", pad=15)
    ax.legend(loc="upper right")

    fig.tight_layout()
    out_file = output_dir / "chart_4_top_categories_by_state.png"
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    logger.info("Saved %s", out_file)
    return out_file

def generate_all_charts() -> List[Path]:
    """Generate all 4 labelled WBR charts."""
    out_dir = config.charts_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating publication-grade charts into %s...", out_dir)

    charts = [
        generate_monthly_revenue_chart(out_dir),
        generate_rolling_orders_chart(out_dir),
        generate_delivery_delay_vs_review_chart(out_dir),
        generate_top_categories_by_state_chart(out_dir)
    ]
    logger.info("Successfully generated %d charts.", len(charts))
    return charts

if __name__ == "__main__":
    generate_all_charts()
