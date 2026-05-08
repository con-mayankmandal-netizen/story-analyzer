import pandas as pd
import re

COLUMN_MAP = {
    "Writers": "writers", "Meta Publishing Week": "publish_week",
    "Daily Budget": "daily_budget", "Budget Cap": "budget_cap",
    "Geography": "geography", "Unique Name": "unique_name",
    "Asset Length": "asset_length", "Adset Code": "adset_code",
    "Adset Name": "adset_name", "Meta Link(Ad name)": "meta_link",
    "Campaign": "campaign", "Script Name": "script_name",
    "Results": "results", "Result indicator": "result_indicator",
    "Reach": "reach", "Impressions": "impressions",
    "Cost per results": "cost_per_result", "Amount spent (USD)": "spend_usd",
    "3 Sec Play": "three_sec_play", "ThruPlay %": "thruplays_pct",
    "ThruPlays %": "thruplays_pct", "V 0% - 25%": "v0_25",
    "Video - 0% - 25%": "v0_25", "V 25% - 50%": "v25_50",
    "Video - 25% - 50%": "v25_50", "V 50% - 75%": "v50_75",
    "Video - 50% - 75%": "v50_75", "V 75% - 95%": "v75_95",
    "Video - 75% - 95%": "v75_95", "V 0% - 95%": "v0_95",
    "Video - 0% - 95%": "v0_95", "CTR": "ctr",
    "CTR (link click-through rate)": "ctr", "CTI": "cti",
    "Click to Install": "cti", "CTR * CTI": "ctr_x_cti",
    "CPM": "cpm", "CPM (cost per 1,000 impressions) (USD)": "cpm",
    "Activation %": "activation_pct",
    "0-95% Completion / ThruPlays": "completion_thruplays",
    "CPM/CTR": "cpm_ctr_ratio",
}

SUM_COLS = ["results", "reach", "impressions", "spend_usd"]
MEAN_COLS = [
    "cost_per_result", "three_sec_play", "thruplays_pct",
    "v0_25", "v25_50", "v50_75", "v75_95", "v0_95",
    "ctr", "cti", "ctr_x_cti", "cpm", "activation_pct",
    "completion_thruplays", "cpm_ctr_ratio",
]


def _extract_adset_code(ad_name):
    m = re.search(r"(GAI\d+)", str(ad_name))
    return m.group(1) if m else None


def load_and_aggregate(uploaded_file):
    warnings = []
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    rename = {col: COLUMN_MAP[col] for col in df.columns if col in COLUMN_MAP}
    df = df.rename(columns=rename)

    if "adset_code" not in df.columns:
        if "adset_name" in df.columns:
            df["adset_code"] = df["adset_name"].apply(_extract_adset_code)
            warnings.append("Adset Code extracted from Ad name.")
        elif "Ad name" in df.columns:
            df["adset_code"] = df["Ad name"].apply(_extract_adset_code)
            warnings.append("Adset Code extracted from Ad name.")
        else:
            raise ValueError("Cannot find Adset Code column.")

    df["adset_code"] = df["adset_code"].astype(str).str.strip()

    if "cpm_ctr_ratio" not in df.columns and "cpm" in df.columns and "ctr" in df.columns:
        df["cpm_ctr_ratio"] = df["cpm"] / df["ctr"].replace(0, float("nan"))

    agg_dict = {}
    for col in SUM_COLS:
        if col in df.columns:
            agg_dict[col] = "sum"
    for col in MEAN_COLS:
        if col in df.columns:
            agg_dict[col] = "mean"

    meta_cols = ["writers", "publish_week", "daily_budget", "budget_cap",
                 "geography", "unique_name", "asset_length", "adset_name",
                 "meta_link", "campaign", "script_name"]
    for col in meta_cols:
        if col in df.columns:
            agg_dict[col] = "first"

    aggregated = df.groupby("adset_code", as_index=False).agg(agg_dict)

    if "spend_usd" in aggregated.columns and "results" in aggregated.columns:
        aggregated["cost_per_result"] = (
            aggregated["spend_usd"] / aggregated["results"].replace(0, float("nan"))
        )

    return aggregated, warnings


def get_available_adset_codes(df):
    return sorted(df["adset_code"].dropna().unique().tolist())


def get_metrics_for_code(df, code):
    row = df[df["adset_code"] == code]
    if row.empty:
        return {}
    return row.iloc[0].dropna().to_dict()


def metrics_summary_text(metrics):
    lines = []
    field_labels = {
        "writers": "Writer(s)", "publish_week": "Publish Week",
        "geography": "Geography", "asset_length": "Asset Length",
        "spend_usd": "Total Spend (USD)", "results": "Total Installs",
        "cost_per_result": "CPI (USD)", "reach": "Reach",
        "impressions": "Impressions", "cpm": "CPM (USD)",
        "ctr": "CTR (%)", "cti": "CTI (%)", "ctr_x_cti": "CTR x CTI",
        "cpm_ctr_ratio": "CPM/CTR", "three_sec_play": "3-Sec Play Rate",
        "thruplays_pct": "ThruPlay %", "v0_25": "Video 0-25%",
        "v25_50": "Video 25-50%", "v50_75": "Video 50-75%",
        "v75_95": "Video 75-95%", "v0_95": "Video 0-95%",
        "activation_pct": "Activation %",
        "completion_thruplays": "0-95% Completion/ThruPlays",
        "daily_budget": "Daily Budget (USD)", "budget_cap": "Budget Cap (USD)",
    }
    for key, label in field_labels.items():
        val = metrics.get(key)
        if val is not None and str(val) not in ("nan", "None", ""):
            if isinstance(val, float):
                lines.append(f"{label}: {val:.4f}")
            else:
                lines.append(f"{label}: {val}")
    return "\n".join(lines)
