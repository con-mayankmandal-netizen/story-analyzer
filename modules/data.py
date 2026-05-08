"""
Data processor.
Reads the master Excel (all columns pre-filled by user),
aggregates multi-week rows by Adset Code,
returns clean dicts for Claude analysis.
"""

import pandas as pd
import re

COLUMN_MAP = {
    "Writers":"writers","Meta Publishing Week":"publish_week","Daily Budget":"daily_budget","Budget Cap":"budget_cap","Geography":"geography","Unique Name":"unique_name","Asset Length":"asset_length","Adset Code":"adset_code","Adset Name":"adset_name","Meta Link(Ad name)":"meta_link","Campaign":"campaign","Script Name":"script_name","Results":"results","Result indicator":"result_indicator","Reach":"reach","Impressions":"impressions","Cost per results":"cost_per_result","Amount spent (USD)":"spend_usd","3 Sec Play":"three_sec_play","ThruPlay %":"thruplays_pct","ThruPlays %":"thruplays_pct","V 0% - 25%":"v0_25","Video - 0% - 25%":"v0_25","V 25% - 50%":"v25_50","Video - 25% - 50%":"v25_50","V 50% - 75%":"v50_75","Video - 50% - 75%":"v50_75","V 75% - 95%":"v75_95","Video - 75% - 95%":"v75_95","V 0% - 95%":"v0_95","Video - 0% - 95%":"v0_95","CTR":"ctr","CTR (link click-through rate)":"ctr","CTI":"cti","Click to Install":"cti","CTR * CTI":"ctr_x_cti","CPM":"cpm","CPM (cost per 1,000 impressions) (USD)":"cpm","Activation %":"activation_pct","0-95% Completion / ThruPlays":"completion_thruplays","CPM/CTR":"cpm_ctr_ratio"}
SUM_COLS=["results","reach","impressions","spend_usd"]
MEAN_COLS=["cost_per_result","three_sec_play","thruplays_pct","v0_25","v25_50","v50_75","v75_95","v0_95","ctr","cti","ctr_x_cti","cpm","activation_pct","completion_thruplays","cpm_ctr_ratio"]

def _extract_adset_code(n):
    m=re.search(r"(GAI\d+)",str(n));return m.group(1) if m else None

def load_and_aggregate(f):
    w=[];df=pd.read_excel(f,engine="openpyxl")
    df=df.rename(columns={c:COLUMN_MAP[c] for c in df.columns if c in COLUMN_MAP})
    if "adset_code" not in df.columns:
        k="adset_name" if "adset_name" in df.columns else "Ad name"
        if k not in df.columns: raise ValueError("No Adset Code column")
        df["adset_code"]=df[k].apply(_extract_adset_code);w.append("Adset Code extracted from Ad name")
    df["adset_code"]=df["adset_code"].astype(str).str.strip()
    if "cpm_ctr_ratio" not in df.columns and "cpm" in df.columns and "ctr" in df.columns:
        df["cpm_ctr_ratio"]=df["cpm"]/df["ctr"].replace(0,float("nan"))
    a={}
    for c in SUM_COLS:
        if c in df.columns: a[c]="sum"
    for c in MEAN_COLS:
        if c in df.columns: a[c]="mean"
    for c in ["writers","publish_week","daily_budget","budget_cap","geography","unique_name","asset_length","adset_name","meta_link","campaign","script_name"]:
        if c in df.columns: a[c]="first"
    ag=df.groupby("adset_code",as_index=False).agg(a)
    if "spend_usd" in ag.columns and "results" in ag.columns:
        ag["cost_per_result"]=ag["spend_usd"]/ag["results"].replace(0,float("nan"))
    return ag,w

def get_available_adset_codes(df): return sorted(df["adset_code"].dropna().unique().tolist())
def get_metrics_for_code(df,c):
    r=df[df["adset_code"]==c];return {} if r.empty else r.iloc[0].dropna().to_dict()
def metrics_summary_text(m):
    l={"writers":"Writer(s)","publish_week":"Week","geography":"Geo","asset_length":"Length","spend_usd":"Spend","results":"Installs","cost_per_result":"CPI","reach":"Reach","impressions":"Impressions","cpm":"CPM","ctr":"CTR","cti":"CTI","ctr_x_cti":"CTRxCTI","cpm_ctr_ratio":"CPM/CTR","three_sec_play":"3Sec","thruplays_pct":"ThruPlay%","v0_25":"V0-25%","v25_50":"V25-50%","v50_75":"V50-75%","v75_95":"V75-95%","v0_95":"V0-95%","activation_pct":"Activation%","completion_thruplays":"Completion/ThruPlays","daily_budget":"DailyBudget","budget_cap":"BudgetCap"}
    return "\n".join([f"{l[k]}: {v:.4f}" if isinstance(v=m.get(k),float) else f"{l[k]}: {v}" for k in l if m.get(k) not in (None, float("nan")) and str(m.get(k)) not in ("nan","None","")])
