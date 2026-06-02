"""
Healthcare Risk Population Dashboard
=====================================
Claims-based population health risk stratification analytics
built on CMS Medicare SynPUF data.

Setup (secrets.toml):
    [gcp]
    project_id = "your-gcp-project"
    credentials = { ... }  # Service account JSON as dict

Or use Application Default Credentials (gcloud auth application-default login).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google.cloud import bigquery
from google.oauth2 import service_account
import json

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Healthcare Risk Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
COLORS = {
    "primary":     "#1B4F72",
    "positive":    "#2ECC71",
    "alert":       "#E74C3C",
    "warning":     "#F39C12",
    "neutral":     "#95A5A6",
    "high":        "#E74C3C",
    "rising_cost": "#F39C12",
    "moderate":    "#3498DB",
    "low":         "#2ECC71",
}

TIER_COLORS = {
    "high":        COLORS["high"],
    "rising_cost": COLORS["rising_cost"],
    "moderate":    COLORS["moderate"],
    "low":         COLORS["low"],
}

TIER_ORDER = ["high", "rising_cost", "moderate", "low"]

# ---------------------------------------------------------------------------
# BigQuery client
# ---------------------------------------------------------------------------
@st.cache_resource
def get_bq_client():
    import os
    try:
        # Streamlit Cloud — flat secrets
        if "service_account_json" in st.secrets:
            import json
            creds_info = json.loads(st.secrets["service_account_json"])
            project = st.secrets.get("project_id", "healthcare-risk-vinay")
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
            return bigquery.Client(credentials=creds, project=project)

        # Local laptop — key file
        key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if key_path and os.path.exists(key_path):
            project = st.secrets.get("project_id") or \
                      st.secrets.get("gcp", {}).get("project_id") or \
                      os.getenv("GCP_PROJECT_ID", "healthcare-risk-vinay")
            creds = service_account.Credentials.from_service_account_file(
                key_path,
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
            return bigquery.Client(credentials=creds, project=project)

        # ADC fallback
        project = st.secrets.get("project_id") or \
                  st.secrets.get("gcp", {}).get("project_id") or \
                  os.getenv("GCP_PROJECT_ID", "healthcare-risk-vinay")
        return bigquery.Client(project=project)

    except Exception as e:
        st.error(f"BigQuery connection failed: {e}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def query_bq(sql: str) -> pd.DataFrame:
    client = get_bq_client()
    if client is None:
        return pd.DataFrame()
    try:
        df = client.query(sql).to_dataframe()
        import decimal
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check the first non-null element to see if it is a Decimal
                non_nulls = df[col].dropna()
                if not non_nulls.empty and isinstance(non_nulls.iloc[0], decimal.Decimal):
                    df[col] = df[col].astype(float)
        return df
    except Exception as e:
        st.warning(f"Query failed: {e}")
        return pd.DataFrame()


def get_project() -> str:
    import os
    try:
        project = st.secrets.get("project_id") or \
                  st.secrets.get("gcp", {}).get("project_id") or \
                  os.getenv("GCP_PROJECT_ID")
        if project:
            return project
            
        local_key = "C:/projects/healthcare_risk/gcp-json-key.json"
        if os.path.exists(local_key):
            try:
                with open(local_key, "r") as f:
                    import json
                    key_data = json.load(f)
                    return key_data.get("project_id", "healthcare-risk-vinay")
            except Exception:
                pass
        return "healthcare-risk-vinay"
    except Exception:
        return "healthcare-risk-vinay"


def get_dataset() -> str:
    import os
    try:
        return st.secrets.get("dataset") or \
               st.secrets.get("gcp", {}).get("dataset") or \
               os.getenv("GCP_DATASET", "healthcare_risk_dev_marts")
    except Exception:
        return "healthcare_risk_dev_marts"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_risk_profiles(year: int) -> pd.DataFrame:
    p = get_project()
    d = get_dataset()
    return query_bq(f"""
        SELECT *
        FROM `{p}.{d}.mart_member_risk_profile`
        WHERE measurement_year = {year}
    """)


@st.cache_data(ttl=3600)
def load_care_gaps(year: int) -> pd.DataFrame:
    p = get_project()
    d = get_dataset()
    return query_bq(f"""
        SELECT cg.*, rp.risk_tier
        FROM `{p}.{d}.mart_care_gaps` cg
        LEFT JOIN `{p}.{d}.mart_member_risk_profile` rp
            ON cg.member_id = rp.member_id
            AND rp.measurement_year = {year}
        WHERE cg.measurement_year = {year}
    """)


@st.cache_data(ttl=3600)
def load_cost_utilization(year: int) -> pd.DataFrame:
    p = get_project()
    d = get_dataset()
    return query_bq(f"""
        SELECT *
        FROM `{p}.{d}.mart_cost_utilization`
        WHERE measurement_year = {year}
        ORDER BY avg_cost_pmpm DESC
    """)


@st.cache_data(ttl=3600)
def load_provider_efficiency() -> pd.DataFrame:
    p = get_project()
    d = get_dataset()
    df = query_bq(f"""
        SELECT *
        FROM `{p}.{d}.mart_provider_efficiency`
        ORDER BY attributed_member_count DESC
        LIMIT 200
    """)
    if not df.empty and "attributed_member_count" in df.columns:
        df["attributed_member_count"] = df["attributed_member_count"].astype(float)
    return df


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/heart-with-pulse.png", width=60)
    st.title("Healthcare Risk Analytics")
    st.caption("Synthea synthetic EHR · Claims-Based Population Health")
    st.divider()

    year = st.selectbox("Measurement Year", options=[2023], index=0)
    st.divider()
    
    st.subheader("🔌 GCP BigQuery Status")
    st.success("Connected", icon="🟢")
    st.info(f"**Project:** `{get_project()}`\n\n**Dataset:** `{get_dataset()}`")
    st.divider()
    
    st.caption("Built with BigQuery · dbt · Streamlit")
    st.caption("Data: Synthea Synthetic EHR")
    st.warning("⚠️ Synthetic data only. Not for clinical use.", icon="⚠️")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🏘️ Population Overview",
    "🩺 Care Gap Analysis",
    "💰 Cost & Utilization",
    "👨‍⚕️ Provider Efficiency",
])

# ===========================================================================
# TAB 1: Population Overview
# ===========================================================================
with tab1:
    st.header("Population Overview", divider="blue")

    with st.spinner("Loading population data..."):
        df_risk = load_risk_profiles(year)

    if df_risk.empty:
        st.warning("No population data found. Ensure BigQuery tables are populated.")
        st.stop()

    # KPI row
    total_members   = len(df_risk)
    high_risk       = len(df_risk[df_risk["risk_tier"] == "high"])
    avg_hcc         = df_risk["hcc_risk_score"].mean()
    avg_pmpm        = df_risk["cost_pmpm"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Members",     f"{total_members:,}")
    col2.metric("High-Risk Members", f"{high_risk:,}",
                delta=f"{high_risk/total_members*100:.1f}% of population",
                delta_color="inverse")
    col3.metric("Avg HCC Score",     f"{avg_hcc:.3f}")
    col4.metric("Avg Cost PMPM",     f"${avg_pmpm:,.0f}")

    st.divider()
    col_left, col_right = st.columns([1, 1.6])

    with col_left:
        st.subheader("Risk Tier Distribution")
        tier_counts = (
            df_risk["risk_tier"]
            .value_counts()
            .reindex(TIER_ORDER, fill_value=0)
            .reset_index()
        )
        tier_counts.columns = ["risk_tier", "count"]
        fig_donut = px.pie(
            tier_counts,
            values="count",
            names="risk_tier",
            hole=0.5,
            color="risk_tier",
            color_discrete_map=TIER_COLORS,
            category_orders={"risk_tier": TIER_ORDER},
        )
        fig_donut.update_traces(textinfo="percent+label")
        fig_donut.update_layout(
            showlegend=True,
            margin=dict(t=20, b=20, l=20, r=20),
            height=320,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        st.subheader("Top 10 Conditions by Prevalence")
        condition_cols = [c for c in df_risk.columns if c.startswith("cc_")]
        if condition_cols:
            condition_rates = (
                df_risk[condition_cols]
                .mean()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            condition_rates.columns = ["condition", "prevalence"]
            condition_rates["condition"] = (
                condition_rates["condition"]
                .str.replace("cc_", "", regex=False)
                .str.replace("_", " ", regex=False)
                .str.title()
            )
            condition_rates["prevalence_pct"] = condition_rates["prevalence"] * 100

            fig_bar = px.bar(
                condition_rates,
                x="prevalence_pct",
                y="condition",
                orientation="h",
                color="prevalence_pct",
                color_continuous_scale=["#AED6F1", "#1B4F72"],
                labels={"prevalence_pct": "Prevalence (%)", "condition": ""},
            )
            fig_bar.update_layout(
                coloraxis_showscale=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=320,
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # HCC score distribution by tier
    st.subheader("HCC Risk Score Distribution by Tier")
    fig_box = px.box(
        df_risk[df_risk["hcc_risk_score"] > 0],
        x="risk_tier",
        y="hcc_risk_score",
        color="risk_tier",
        color_discrete_map=TIER_COLORS,
        category_orders={"risk_tier": TIER_ORDER},
        labels={"hcc_risk_score": "HCC Risk Score", "risk_tier": "Risk Tier"},
        points="outliers",
    )
    fig_box.update_layout(showlegend=False, height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig_box, use_container_width=True)


# ===========================================================================
# TAB 2: Care Gap Analysis
# ===========================================================================
with tab2:
    st.header("Care Gap Analysis", divider="blue")
    st.caption("HEDIS-adjacent measures. NOT NCQA-certified.")

    with st.spinner("Loading care gap data..."):
        df_gaps = load_care_gaps(year)

    if df_gaps.empty:
        st.warning("No care gap data found.")
        st.stop()

    total_gaps  = len(df_gaps)
    open_gaps   = df_gaps["gap_open"].sum()
    overall_gap_rate = open_gaps / total_gaps * 100 if total_gaps > 0 else 0

    high_risk_gaps = df_gaps[df_gaps["risk_tier"] == "high"]
    hr_gap_rate = (
        high_risk_gaps["gap_open"].mean() * 100
        if not high_risk_gaps.empty else 0
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Gap Opportunities", f"{total_gaps:,}")
    col2.metric("Overall Open Gap Rate",   f"{overall_gap_rate:.1f}%")
    col3.metric("High-Risk Member Gap Rate", f"{hr_gap_rate:.1f}%",
                delta="Most actionable", delta_color="off")

    st.divider()

    # Gap rate by gap type and risk tier
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Gap Rate by Type & Risk Tier")
        gap_by_tier = (
            df_gaps.groupby(["gap_type", "risk_tier"])["gap_open"]
            .mean()
            .reset_index()
        )
        gap_by_tier["gap_rate_pct"] = gap_by_tier["gap_open"] * 100
        gap_by_tier["gap_type_label"] = (
            gap_by_tier["gap_type"]
            .str.replace("_", " ", regex=False)
            .str.title()
        )

        fig_grouped = px.bar(
            gap_by_tier,
            x="gap_type_label",
            y="gap_rate_pct",
            color="risk_tier",
            barmode="group",
            color_discrete_map=TIER_COLORS,
            category_orders={"risk_tier": TIER_ORDER},
            labels={"gap_rate_pct": "Open Gap Rate (%)", "gap_type_label": "Gap Type"},
        )
        fig_grouped.update_layout(height=350, margin=dict(t=20, b=60))
        st.plotly_chart(fig_grouped, use_container_width=True)

    with col_right:
        st.subheader("Gap Summary Table")
        summary = (
            df_gaps.groupby("gap_type")
            .agg(
                eligible_members=("member_id", "nunique"),
                open_gaps=("gap_open", "sum"),
                gap_rate=("gap_open", "mean"),
            )
            .reset_index()
        )
        summary["gap_rate"] = (summary["gap_rate"] * 100).round(1)
        summary["gap_type"] = (
            summary["gap_type"]
            .str.replace("_", " ", regex=False)
            .str.title()
        )
        summary.columns = ["Gap Type", "Eligible Members", "Open Gaps", "Gap Rate (%)"]
        st.dataframe(
            summary.sort_values("Gap Rate (%)", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        csv = summary.to_csv(index=False)
        st.download_button(
            "⬇️ Download Gap Data",
            data=csv,
            file_name=f"care_gaps_{year}.csv",
            mime="text/csv",
        )

    # Heatmap: condition cohort × gap type
    st.subheader("Care Gap Heatmap — Risk Tier × Gap Type")
    if "risk_tier" in df_gaps.columns:
        heatmap_data = (
            df_gaps.groupby(["risk_tier", "gap_type"])["gap_open"]
            .mean()
            .reset_index()
            .pivot(index="risk_tier", columns="gap_type", values="gap_open")
            .reindex(TIER_ORDER)
            * 100
        )

        fig_heat = px.imshow(
            heatmap_data,
            color_continuous_scale=["#2ECC71", "#F39C12", "#E74C3C"],
            labels={"color": "Gap Rate (%)"},
            text_auto=".1f",
            aspect="auto",
        )
        fig_heat.update_layout(height=280, margin=dict(t=20, b=20))
        st.plotly_chart(fig_heat, use_container_width=True)


# ===========================================================================
# TAB 3: Cost & Utilization
# ===========================================================================
with tab3:
    st.header("Cost & Utilization", divider="blue")

    with st.spinner("Loading cost data..."):
        df_cost = load_cost_utilization(year)
        df_risk3 = load_risk_profiles(year)

    if df_cost.empty:
        st.warning("No cost utilization data found.")
        st.stop()

    # KPIs
    total_cost = df_cost["total_cost_ytd"].sum()
    high_row   = df_cost[df_cost["risk_tier"] == "high"]
    high_pmpm  = high_row["avg_cost_pmpm"].values[0] if not high_row.empty else 0
    low_row    = df_cost[df_cost["risk_tier"] == "low"]
    low_pmpm   = low_row["avg_cost_pmpm"].values[0]  if not low_row.empty  else 0
    cost_ratio = high_pmpm / low_pmpm if low_pmpm > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Population Cost",    f"${total_cost:,.0f}")
    col2.metric("High-Risk Avg PMPM",       f"${high_pmpm:,.0f}")
    col3.metric("High vs Low Risk Cost",    f"{cost_ratio:.1f}x",
                delta="High risk costs more", delta_color="inverse")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Avg Cost PMPM by Risk Tier")
        fig_pmpm = px.bar(
            df_cost.sort_values("avg_cost_pmpm", ascending=False),
            x="risk_tier",
            y="avg_cost_pmpm",
            color="risk_tier",
            color_discrete_map=TIER_COLORS,
            category_orders={"risk_tier": TIER_ORDER},
            text="avg_cost_pmpm",
            labels={"avg_cost_pmpm": "Avg Cost PMPM ($)", "risk_tier": "Risk Tier"},
        )
        fig_pmpm.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig_pmpm.update_layout(showlegend=False, height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig_pmpm, use_container_width=True)

    with col_right:
        st.subheader("IP Admits & ER Visits per 1,000")
        fig_util = go.Figure()
        for tier in TIER_ORDER:
            row = df_cost[df_cost["risk_tier"] == tier]
            if row.empty:
                continue
            fig_util.add_trace(go.Bar(
                name=f"{tier} — IP",
                x=[tier],
                y=row["ip_admits_per_1000"].values,
                marker_color=TIER_COLORS.get(tier, "#95A5A6"),
                opacity=0.9,
            ))
            fig_util.add_trace(go.Bar(
                name=f"{tier} — ER",
                x=[tier],
                y=row["er_visits_per_1000"].values,
                marker_color=TIER_COLORS.get(tier, "#95A5A6"),
                opacity=0.5,
                marker_pattern_shape="/",
            ))
        fig_util.update_layout(
            barmode="group",
            height=350,
            margin=dict(t=20, b=20),
            yaxis_title="Events per 1,000 Members",
        )
        st.plotly_chart(fig_util, use_container_width=True)

    # Scatter: HCC score vs cost PMPM
    st.subheader("HCC Risk Score vs Cost PMPM (Member-Level Sample)")
    sample = df_risk3.sample(min(2000, len(df_risk3)), random_state=42)
    fig_scatter = px.scatter(
        sample,
        x="hcc_risk_score",
        y="cost_pmpm",
        color="risk_tier",
        color_discrete_map=TIER_COLORS,
        category_orders={"risk_tier": TIER_ORDER},
        opacity=0.5,
        labels={
            "hcc_risk_score": "HCC Risk Score",
            "cost_pmpm": "Cost PMPM ($)",
            "risk_tier": "Risk Tier",
        },
        hover_data=["member_id", "condition_count", "age_at_year_end"],
    )
    fig_scatter.update_layout(height=400, margin=dict(t=20, b=20))
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Auto-insight
    if not df_cost.empty:
        highest_cost_tier = df_cost.loc[df_cost["avg_cost_pmpm"].idxmax(), "risk_tier"]
        highest_pmpm = df_cost["avg_cost_pmpm"].max()
        pct_of_pop = df_cost.loc[df_cost["avg_cost_pmpm"].idxmax(), "pct_of_population"]
        st.info(
            f"💡 **Key Insight:** The **{highest_cost_tier}** risk tier drives the highest average "
            f"cost at **${highest_pmpm:,.0f} PMPM**, representing **{pct_of_pop:.1f}%** of the "
            f"population but a disproportionate share of total spend."
        )


# ===========================================================================
# TAB 4: Provider Efficiency
# ===========================================================================
with tab4:
    st.header("Provider Efficiency Scorecard", divider="blue")

    with st.spinner("Loading provider data..."):
        df_prov = load_provider_efficiency()

    if df_prov.empty:
        st.warning("No provider data found.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("Providers Analyzed", f"{len(df_prov):,}")
    col2.metric(
        "High Value Providers",
        f"{len(df_prov[df_prov['efficiency_quadrant'] == 'High Value']):,}",
    )
    col3.metric(
        "Avg Gap Closure Rate",
        f"{df_prov['gap_closure_rate_pct'].mean():.1f}%",
    )

    st.divider()

    # Quadrant scatter
    st.subheader("Provider Efficiency Quadrant")
    st.caption(
        "X-axis: HCC-adjusted risk score  ·  Y-axis: Cost PMPM  ·  "
        "Bubble size: Attributed members  ·  Lines: Population medians"
    )

    quadrant_colors = {
        "High Value":       COLORS["positive"],
        "Low Value":        COLORS["alert"],
        "Complex High Cost":COLORS["warning"],
        "Complex Managed":  COLORS["primary"],
    }

    fig_quad = px.scatter(
        df_prov,
        x="avg_hcc_score",
        y="avg_cost_pmpm",
        size="attributed_member_count",
        color="efficiency_quadrant",
        color_discrete_map=quadrant_colors,
        hover_data=["provider_npi", "attributed_member_count",
                    "gap_closure_rate_pct", "top_condition"],
        labels={
            "avg_hcc_score": "Avg HCC Risk Score",
            "avg_cost_pmpm": "Avg Cost PMPM ($)",
            "efficiency_quadrant": "Quadrant",
        },
        size_max=40,
    )

    # Add median lines
    med_cost = df_prov["avg_cost_pmpm"].median()
    med_hcc  = df_prov["avg_hcc_score"].median()

    fig_quad.add_hline(y=med_cost, line_dash="dash", line_color="gray",
                       annotation_text=f"Median PMPM ${med_cost:,.0f}")
    fig_quad.add_vline(x=med_hcc,  line_dash="dash", line_color="gray",
                       annotation_text=f"Median HCC {med_hcc:.2f}")

    fig_quad.update_layout(height=500, margin=dict(t=20, b=20))
    st.plotly_chart(fig_quad, use_container_width=True)

    # Sortable scorecard table
    st.subheader("Provider Scorecard Table")

    cols_display = [
        "provider_npi", "attributed_member_count", "avg_cost_pmpm",
        "avg_hcc_score", "gap_closure_rate_pct", "top_condition",
        "efficiency_quadrant",
    ]
    df_display = df_prov[cols_display].copy()
    df_display.columns = [
        "NPI", "Members", "Avg PMPM ($)", "Avg HCC Score",
        "Gap Closure (%)", "Top Condition", "Quadrant",
    ]
    df_display["Avg PMPM ($)"] = df_display["Avg PMPM ($)"].astype(float).round(0)
    df_display["Avg HCC Score"] = df_display["Avg HCC Score"].astype(float).round(3)

    # Color quadrant column
    def color_quadrant(val):
        colors_map = {
            "High Value": "background-color: #d5f5e3",
            "Low Value": "background-color: #fadbd8",
            "Complex High Cost": "background-color: #fdebd0",
            "Complex Managed": "background-color: #d6eaf8",
        }
        return colors_map.get(val, "")

    st.dataframe(
        df_display.style.map(color_quadrant, subset=["Quadrant"]),
        use_container_width=True,
        hide_index=True,
        height=400,
    )
