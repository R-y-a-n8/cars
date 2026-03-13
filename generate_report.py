"""
Procurement Report Generator
Produces a self-contained HTML report with interactive Plotly charts.
"""

import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
from procurement_data import get_purchase_orders, get_kes_equivalent

# ── Colour palette ──────────────────────────────────────────────────────────
PRIMARY      = "#1a3a5c"
SECONDARY    = "#2e7d9e"
ACCENT       = "#f0a500"
SUCCESS      = "#27ae60"
WARNING      = "#e67e22"
DANGER       = "#c0392b"
LIGHT_BG     = "#f4f7fc"
CARD_BG      = "#ffffff"

CATEGORY_COLORS = px.colors.qualitative.Set2
STATUS_COLORS = {
    "Received":           SUCCESS,
    "Partially Received": WARNING,
    "Pending":            DANGER,
}

CHART_CONFIG = {"displayModeBar": False, "responsive": True}


# ── Data preparation ─────────────────────────────────────────────────────────
def prepare_data(df: pd.DataFrame) -> dict:
    totals = {}

    # By supplier (KES equivalent)
    by_supplier = (
        df.groupby("supplier_name")["amount_kes"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    by_supplier.columns = ["supplier", "amount_kes"]

    # By category
    by_category = (
        df.groupby("category")["amount_kes"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    by_category.columns = ["category", "amount_kes"]

    # By status
    by_status = (
        df.groupby("status")["amount_kes"]
        .sum()
        .reset_index()
    )
    by_status.columns = ["status", "amount_kes"]

    # By currency (original amounts)
    by_currency = (
        df.groupby("currency")["amount"]
        .sum()
        .reset_index()
    )
    by_currency.columns = ["currency", "amount"]

    # Monthly spend
    df["month"] = df["order_date"].dt.to_period("M").astype(str)
    by_month = (
        df.groupby("month")["amount_kes"]
        .sum()
        .reset_index()
    )

    # Order count by supplier
    order_count = (
        df.groupby("supplier_name")["order_id"]
        .count()
        .sort_values(ascending=False)
        .reset_index()
    )
    order_count.columns = ["supplier", "order_count"]

    # Delivery performance
    df["on_time"] = df["delivery_date"] >= df["order_date"] + pd.Timedelta(days=7)
    delivery = df.groupby("status").size().reset_index()
    delivery.columns = ["status", "count"]

    totals["grand_total_kes"] = df["amount_kes"].sum()
    totals["order_count"]     = df["order_id"].nunique()
    totals["supplier_count"]  = df["supplier_name"].nunique()
    totals["received_pct"]    = (
        df[df["status"] == "Received"]["amount_kes"].sum()
        / df["amount_kes"].sum() * 100
    )

    return {
        "df": df,
        "by_supplier":  by_supplier,
        "by_category":  by_category,
        "by_status":    by_status,
        "by_currency":  by_currency,
        "by_month":     by_month,
        "order_count":  order_count,
        "delivery":     delivery,
        "totals":       totals,
    }


# ── Chart builders ────────────────────────────────────────────────────────────
def chart_spend_by_supplier(data: dict) -> str:
    df = data["by_supplier"].copy()
    df["amount_m"] = df["amount_kes"] / 1_000_000
    df["label"] = df["amount_kes"].apply(lambda v: f"KES {v:,.0f}")

    fig = go.Figure(
        go.Bar(
            x=df["amount_m"],
            y=df["supplier"],
            orientation="h",
            marker=dict(
                color=df["amount_kes"],
                colorscale=[[0, SECONDARY], [1, PRIMARY]],
                showscale=False,
            ),
            text=df["label"],
            textposition="outside",
            textfont=dict(size=11),
            hovertemplate="<b>%{y}</b><br>KES %{x:.2f}M<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Total Spend by Supplier (KES Equivalent)", font=dict(size=15, color=PRIMARY)),
        xaxis=dict(title="Amount (Millions KES)", tickprefix="KES ", tickformat=".1f"),
        yaxis=dict(autorange="reversed"),
        height=480,
        margin=dict(l=220, r=160, t=50, b=40),
        plot_bgcolor=LIGHT_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_spend_by_category(data: dict) -> str:
    df = data["by_category"]
    fig = go.Figure(
        go.Pie(
            labels=df["category"],
            values=df["amount_kes"],
            hole=0.45,
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>KES %{value:,.0f}<br>%{percent}<extra></extra>",
            marker=dict(colors=CATEGORY_COLORS),
        )
    )
    fig.update_layout(
        title=dict(text="Procurement Spend by Category", font=dict(size=15, color=PRIMARY)),
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
        legend=dict(orientation="v", x=1.02, y=0.5),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_order_status(data: dict) -> str:
    df = data["by_status"]
    colors = [STATUS_COLORS.get(s, SECONDARY) for s in df["status"]]
    fig = go.Figure(
        go.Bar(
            x=df["status"],
            y=df["amount_kes"] / 1_000,
            marker_color=colors,
            text=[f"KES {v/1_000:,.0f}K" for v in df["amount_kes"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>KES %{y:,.0f}K<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Order Value by Status", font=dict(size=15, color=PRIMARY)),
        yaxis=dict(title="Amount (KES Thousands)", ticksuffix="K"),
        xaxis=dict(title="Order Status"),
        height=360,
        margin=dict(l=60, r=60, t=50, b=40),
        plot_bgcolor=LIGHT_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_monthly_spend(data: dict) -> str:
    df = data["by_month"]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["month"],
            y=df["amount_kes"] / 1_000_000,
            marker_color=SECONDARY,
            opacity=0.6,
            name="Monthly Spend",
            hovertemplate="<b>%{x}</b><br>KES %{y:.2f}M<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["month"],
            y=df["amount_kes"].cumsum() / 1_000_000,
            mode="lines+markers",
            line=dict(color=ACCENT, width=3),
            marker=dict(size=9, color=ACCENT),
            name="Cumulative Spend",
            yaxis="y2",
            hovertemplate="<b>%{x}</b><br>Cumulative: KES %{y:.2f}M<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Monthly Procurement Spend & Cumulative Trend", font=dict(size=15, color=PRIMARY)),
        xaxis=dict(title="Month"),
        yaxis=dict(title="Monthly (Millions KES)", side="left"),
        yaxis2=dict(title="Cumulative (Millions KES)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", x=0, y=-0.2),
        height=380,
        margin=dict(l=70, r=70, t=50, b=60),
        plot_bgcolor=LIGHT_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_order_count(data: dict) -> str:
    df = data["order_count"]
    fig = go.Figure(
        go.Bar(
            x=df["order_count"],
            y=df["supplier"],
            orientation="h",
            marker_color=ACCENT,
            text=df["order_count"],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} orders<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Number of Purchase Orders per Supplier", font=dict(size=15, color=PRIMARY)),
        xaxis=dict(title="Number of Orders", dtick=1),
        yaxis=dict(autorange="reversed"),
        height=440,
        margin=dict(l=220, r=60, t=50, b=40),
        plot_bgcolor=LIGHT_BG,
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_currency_split(data: dict) -> str:
    df = data["by_currency"]
    fig = go.Figure(
        go.Pie(
            labels=df["currency"],
            values=df["amount"],
            hole=0.0,
            textinfo="label+value+percent",
            texttemplate="%{label}<br>%{value:,.0f}<br>%{percent}",
            hovertemplate="<b>%{label}</b><br>Amount: %{value:,.2f}<br>%{percent}<extra></extra>",
            marker=dict(colors=[PRIMARY, ACCENT, SUCCESS]),
        )
    )
    fig.update_layout(
        title=dict(text="Procurement by Currency (Original Amounts)", font=dict(size=15, color=PRIMARY)),
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_top_orders_table(data: dict) -> str:
    df = data["df"].copy()
    df = df.sort_values("amount_kes", ascending=False).head(10)
    df["amount_kes_fmt"]  = df["amount_kes"].apply(lambda v: f"KES {v:,.0f}")
    df["amount_orig_fmt"] = df.apply(
        lambda r: f"{r['currency']} {r['amount']:,.2f}", axis=1
    )

    status_sym = {
        "Received":           "✔ Received",
        "Partially Received": "◑ Partial",
        "Pending":            "⏳ Pending",
    }

    fig = go.Figure(
        go.Table(
            columnwidth=[100, 250, 130, 150, 120],
            header=dict(
                values=["<b>PO Number</b>", "<b>Supplier</b>",
                        "<b>Category</b>", "<b>Amount (KES)</b>", "<b>Status</b>"],
                fill_color=PRIMARY,
                font=dict(color="white", size=12),
                align="left",
                height=32,
            ),
            cells=dict(
                values=[
                    df["po_number"].tolist(),
                    df["supplier_name"].tolist(),
                    df["category"].tolist(),
                    df["amount_kes_fmt"].tolist(),
                    [status_sym.get(s, s) for s in df["status"].tolist()],
                ],
                fill_color=[
                    ["#f9f9f9" if i % 2 == 0 else CARD_BG for i in range(len(df))]
                ] * 5,
                font=dict(color="#333", size=11),
                align="left",
                height=28,
            ),
        )
    )
    fig.update_layout(
        title=dict(text="Top 10 Purchase Orders by Value", font=dict(size=15, color=PRIMARY)),
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor=CARD_BG,
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


def chart_supplier_heatmap(data: dict) -> str:
    """Status × Category heat-map of spend."""
    df = data["df"]
    pivot = (
        df.pivot_table(
            values="amount_kes",
            index="category",
            columns="status",
            aggfunc="sum",
            fill_value=0,
        )
        / 1_000
    )

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=[[0, "#eaf4fb"], [0.5, SECONDARY], [1, PRIMARY]],
            text=[[f"KES {v:,.0f}K" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            hovertemplate="<b>%{y}</b> | %{x}<br>KES %{z:,.0f}K<extra></extra>",
            showscale=True,
            colorbar=dict(title="KES (Thousands)"),
        )
    )
    fig.update_layout(
        title=dict(text="Spend Heatmap: Category vs. Order Status (KES Thousands)", font=dict(size=15, color=PRIMARY)),
        xaxis=dict(title="Status"),
        yaxis=dict(title="Category"),
        height=420,
        margin=dict(l=180, r=80, t=50, b=50),
        paper_bgcolor=CARD_BG,
        font=dict(family="Segoe UI, Arial", color="#333"),
    )
    return pio.to_html(fig, full_html=False, config=CHART_CONFIG, include_plotlyjs=False)


# ── HTML assembly ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Procurement Report – Purchase Order Analysis</title>
  <script>{plotly_js}</script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 0;
      font-family: 'Segoe UI', Arial, sans-serif;
      background: {light_bg};
      color: #333;
    }}
    /* ── Header ── */
    header {{
      background: linear-gradient(135deg, {primary} 0%, {secondary} 100%);
      color: #fff;
      padding: 2rem 2.5rem 1.5rem;
    }}
    header h1 {{ margin: 0 0 0.3rem; font-size: 1.9rem; letter-spacing: 0.5px; }}
    header p  {{ margin: 0; font-size: 0.95rem; opacity: 0.85; }}
    /* ── KPI cards ── */
    .kpi-row {{
      display: flex; flex-wrap: wrap; gap: 1rem;
      padding: 1.5rem 2rem;
    }}
    .kpi {{
      flex: 1 1 180px;
      background: {card_bg};
      border-radius: 10px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.07);
      padding: 1.2rem 1.5rem;
      text-align: center;
    }}
    .kpi .value {{ font-size: 2rem; font-weight: 700; color: {primary}; }}
    .kpi .label {{ font-size: 0.82rem; text-transform: uppercase;
                   letter-spacing: 1px; color: #777; margin-top: 4px; }}
    .kpi.accent .value {{ color: {accent}; }}
    .kpi.success .value {{ color: {success}; }}
    /* ── Sections ── */
    .section {{
      padding: 0.5rem 2rem 1.5rem;
    }}
    .section h2 {{
      font-size: 1.1rem; text-transform: uppercase;
      letter-spacing: 1.5px; color: {secondary};
      border-left: 4px solid {accent};
      padding-left: 0.7rem; margin: 1.5rem 0 0.8rem;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 1.2rem;
    }}
    .chart-card {{
      background: {card_bg};
      border-radius: 10px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.07);
      padding: 1rem 0.5rem 0.5rem;
      overflow: hidden;
    }}
    .chart-card.full {{ grid-column: 1 / -1; }}
    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 1.5rem;
      font-size: 0.8rem;
      color: #aaa;
      border-top: 1px solid #e0e0e0;
    }}
  </style>
</head>
<body>
<header>
  <h1>Procurement Report &mdash; Purchase Order Analysis</h1>
  <p>Reporting Period: January 2024 &ndash; March 2024 &nbsp;|&nbsp;
     Generated: {report_date} &nbsp;|&nbsp;
     All multi-currency values converted to KES equivalent</p>
</header>

<!-- KPI Cards -->
<div class="kpi-row">
  <div class="kpi">
    <div class="value">{total_kes}</div>
    <div class="label">Total Spend (KES)</div>
  </div>
  <div class="kpi accent">
    <div class="value">{order_count}</div>
    <div class="label">Purchase Orders</div>
  </div>
  <div class="kpi">
    <div class="value">{supplier_count}</div>
    <div class="label">Active Suppliers</div>
  </div>
  <div class="kpi success">
    <div class="value">{received_pct}%</div>
    <div class="label">Fully Received</div>
  </div>
</div>

<!-- Charts -->
<div class="section">

  <h2>Supplier Analysis</h2>
  <div class="chart-grid">
    <div class="chart-card full">{chart_spend_supplier}</div>
    <div class="chart-card full">{chart_order_count}</div>
  </div>

  <h2>Category &amp; Currency Breakdown</h2>
  <div class="chart-grid">
    <div class="chart-card">{chart_category}</div>
    <div class="chart-card">{chart_currency}</div>
  </div>

  <h2>Order Status &amp; Trend</h2>
  <div class="chart-grid">
    <div class="chart-card">{chart_status}</div>
    <div class="chart-card">{chart_monthly}</div>
  </div>

  <h2>Spend Heatmap</h2>
  <div class="chart-grid">
    <div class="chart-card full">{chart_heatmap}</div>
  </div>

  <h2>Top Purchase Orders</h2>
  <div class="chart-grid">
    <div class="chart-card full">{chart_table}</div>
  </div>

</div>

<footer>Procurement Report &copy; 2024 &mdash; Confidential &mdash; For Internal Use Only</footer>
</body>
</html>"""


def build_report(output_path: str = "procurement_report.html"):
    from datetime import date
    from plotly.offline import get_plotlyjs

    raw  = get_purchase_orders()
    df   = get_kes_equivalent(raw)
    data = prepare_data(df)
    t    = data["totals"]

    html = HTML_TEMPLATE.format(
        primary=PRIMARY, secondary=SECONDARY, accent=ACCENT,
        success=SUCCESS, light_bg=LIGHT_BG, card_bg=CARD_BG,
        plotly_js=get_plotlyjs(),
        report_date=date.today().strftime("%d %B %Y"),
        total_kes=f"KES {t['grand_total_kes']:,.0f}",
        order_count=t["order_count"],
        supplier_count=t["supplier_count"],
        received_pct=f"{t['received_pct']:.1f}",
        chart_spend_supplier=chart_spend_by_supplier(data),
        chart_order_count=chart_order_count(data),
        chart_category=chart_spend_by_category(data),
        chart_currency=chart_currency_split(data),
        chart_status=chart_order_status(data),
        chart_monthly=chart_monthly_spend(data),
        chart_heatmap=chart_supplier_heatmap(data),
        chart_table=chart_top_orders_table(data),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report written → {output_path}")
    print(f"  Total POs   : {t['order_count']}")
    print(f"  Suppliers   : {t['supplier_count']}")
    print(f"  Grand Total : KES {t['grand_total_kes']:,.2f}")
    print(f"  Fully Rcvd  : {t['received_pct']:.1f}%")


if __name__ == "__main__":
    build_report()
