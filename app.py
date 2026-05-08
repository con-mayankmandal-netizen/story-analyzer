"""
Story Analyzer — Main Streamlit App
Connects master Excel (all columns) + Google Drive scripts → Claude analysis
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import io

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Story Analyzer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background: #0f0f1a; color: #e2e8f0; }
  .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  h1 { font-size: 1.6rem !important; font-weight: 800 !important; color: #a78bfa !important; }
  h2 { font-size: 1.1rem !important; font-weight: 700 !important; color: #c4b5fd !important; }
  h3 { font-size: 0.95rem !important; font-weight: 600 !important; color: #ddd6fe !important; }
  .metric-card {
    background: #1e1b2e; border: 1px solid #3730a3; border-radius: 10px;
    padding: 14px 18px; text-align: center; margin-bottom: 8px;
  }
  .metric-val { font-size: 1.6rem; font-weight: 900; color: #a78bfa; }
  .metric-label { font-size: 0.72rem; color: #94a3b8; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px; }
  .score-badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 700;
  }
  .insight-card {
    background: linear-gradient(135deg, #1e1b2e 0%, #2d1b69 100%);
    border: 1px solid #5b21b6; border-radius: 10px; padding: 16px; margin-bottom: 12px;
  }
  .finding-row {
    background: #1a1a2e; border-left: 3px solid #7c3aed;
    border-radius: 0 8px 8px 0; padding: 10px 14px; margin-bottom: 8px;
  }
  .rec-row {
    background: #1a2a1a; border-left: 3px solid #16a34a;
    border-radius: 0 8px 8px 0; padding: 10px 14px; margin-bottom: 8px;
  }
  .warning-box {
    background: #2a1a0a; border: 1px solid #d97706;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
    color: #fcd34d; font-size: 0.82rem;
  }
  div[data-testid="stSelectbox"] label { color: #c4b5fd !important; font-size: 0.85rem; }
  div[data-testid="stFileUploader"] label { color: #c4b5fd !important; }
  .stButton > button {
    background: linear-gradient(135deg, #6d28d9, #4f46e5) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; font-weight: 700 !important;
    padding: 0.5rem 1.5rem !important;
  }
  .stButton > button:hover { opacity: 0.9 !important; }
</style>
""", unsafe_allow_html=True)


# ── Imports (after page config) ──────────────────────────────────────────────
from modules.data import (
    load_and_aggregate, get_available_adset_codes,
    get_metrics_for_code, metrics_summary_text
)
from modules.analyzer import init_client, analyze_single, compare_scripts


# ── Helpers ──────────────────────────────────────────────────────────────────
def score_color(score: int) -> str:
    if score >= 75: return "#22c55e"
    if score >= 50: return "#f59e0b"
    return "#ef4444"


def score_label(score: int) -> str:
    if score >= 75: return "Strong"
    if score >= 50: return "Average"
    return "Weak"


def render_score_row(label: str, score: int, finding: str, rec: str):
    col1, col2 = st.columns([1, 4])
    with col1:
        color = score_color(score)
        st.markdown(f"""
        <div style="text-align:center; background:#1e1b2e; border:2px solid {color};
             border-radius:10px; padding:10px 6px; margin-top:4px;">
          <div style="font-size:1.5rem; font-weight:900; color:{color}">{score}</div>
          <div style="font-size:0.65rem; color:#94a3b8; text-transform:uppercase">{label}</div>
          <div style="font-size:0.65rem; color:{color}; font-weight:700">{score_label(score)}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="finding-row">🔍 {finding}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="rec-row">💡 {rec}</div>', unsafe_allow_html=True)


def render_retention_funnel(metrics: dict):
    stages = ["0–25%", "25–50%", "50–75%", "75–95%"]
    keys   = ["v0_25", "v25_50", "v50_75", "v75_95"]
    values = [float(metrics.get(k, 0)) * 100 for k in keys]

    fig = go.Figure(go.Funnel(
        y=stages, x=values,
        textinfo="value+percent initial",
        marker=dict(color=["#ef4444", "#f97316", "#eab308", "#22c55e"]),
        connector=dict(line=dict(color="#3730a3", width=2))
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0", size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        height=220
    )
    st.plotly_chart(fig, use_container_width=True)


def render_radar(analyses: dict):
    cats = ["Hook", "Pacing", "Emotional Arc", "CTA", "Overall"]
    fig = go.Figure()
    colors = ["#a78bfa", "#34d399", "#f87171", "#fbbf24"]

    for i, (code, data) in enumerate(analyses.items()):
        vals = [
            data.get("hook_score", 0),
            data.get("pacing_score", 0),
            data.get("emotional_arc_score", 0),
            data.get("cta_score", 0),
            data.get("overall_score", 0),
        ]
        vals += [vals[0]]
        fig.add_trace(go.Scatterpolar(
            r=vals, theta=cats + [cats[0]],
            fill="toself", name=code,
            line=dict(color=colors[i % len(colors)], width=2),
            fillcolor=colors[i % len(colors)].replace(")", ", 0.15)").replace("rgb", "rgba") if "rgb" in colors[i % len(colors)] else colors[i % len(colors)] + "33"
        ))

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100], color="#94a3b8",
                           gridcolor="#2d2d4e"),
            angularaxis=dict(color="#c4b5fd", gridcolor="#2d2d4e")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        legend=dict(bgcolor="rgba(0,0,0,0.3)", bordercolor="#3730a3"),
        height=320, margin=dict(l=40, r=40, t=20, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)


def export_results(analyses: dict, comparison: dict, df: pd.DataFrame) -> bytes:
    """Export full results to Excel."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        # Sheet 1: Scores summary
        rows = []
        for code, a in analyses.items():
            metrics = get_metrics_for_code(df, code)
            rows.append({
                "Adset Code":     code,
                "Writer":         metrics.get("writers", ""),
                "Overall Score":  a.get("overall_score"),
                "Hook Score":     a.get("hook_score"),
                "Pacing Score":   a.get("pacing_score"),
                "Emotional Arc":  a.get("emotional_arc_score"),
                "CTA Score":      a.get("cta_score"),
                "Verdict":        a.get("verdict"),
                "ThruPlay %":     metrics.get("thruplays_pct"),
                "CTR %":          metrics.get("ctr"),
                "CPI (USD)":      metrics.get("cost_per_result"),
                "Spend (USD)":    metrics.get("spend_usd"),
                "Installs":       metrics.get("results"),
            })
        pd.DataFrame(rows).to_excel(writer, sheet_name="Scores", index=False)

        # Sheet 2: Full analysis text
        text_rows = []
        for code, a in analyses.items():
            text_rows.append({
                "Adset Code":            code,
                "Why It Performed":      a.get("why_it_performed"),
                "Hook Finding":          a.get("hook_finding"),
                "Hook Recommendation":   a.get("hook_recommendation"),
                "Retention Correlation": a.get("retention_correlation"),
                "Top Improvement 1":     a.get("top_3_improvements", ["", "", ""])[0],
                "Top Improvement 2":     a.get("top_3_improvements", ["", "", ""])[1],
                "Top Improvement 3":     a.get("top_3_improvements", ["", "", ""])[2],
                "Writer Feedback":       a.get("writer_feedback"),
            })
        pd.DataFrame(text_rows).to_excel(writer, sheet_name="Analysis", index=False)

        # Sheet 3: Comparison
        if comparison:
            comp_rows = [
                {"Field": "Winner",               "Value": comparison.get("winner")},
                {"Field": "Winner Reason",        "Value": comparison.get("winner_reason")},
                {"Field": "Pattern Insights",     "Value": comparison.get("pattern_insights")},
                {"Field": "Hook Pattern",         "Value": comparison.get("hook_pattern")},
                {"Field": "Writer Pattern",       "Value": comparison.get("writer_pattern")},
                {"Field": "Next Test",            "Value": comparison.get("next_test_recommendation")},
            ]
            for i, item in enumerate(comparison.get("what_to_replicate", []), 1):
                comp_rows.append({"Field": f"Replicate {i}", "Value": item})
            for i, item in enumerate(comparison.get("what_to_avoid", []), 1):
                comp_rows.append({"Field": f"Avoid {i}", "Value": item})
            pd.DataFrame(comp_rows).to_excel(writer, sheet_name="Comparison", index=False)

    return output.getvalue()


# ── App State ────────────────────────────────────────────────────────────────
if "analyses"   not in st.session_state: st.session_state.analyses   = {}
if "comparison" not in st.session_state: st.session_state.comparison = {}
if "df"         not in st.session_state: st.session_state.df         = None
if "scripts"    not in st.session_state: st.session_state.scripts    = {}  # {code: text}


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Setup")

    # AI Provider selection
    provider = st.selectbox(
        "AI Provider",
        options=["gemini", "groq", "claude"],
        index=0,
        format_func=lambda x: {
            "gemini": "🟢 Google Gemini (FREE)",
            "groq":   "🟡 Groq / Llama 3.1 (FREE)",
            "claude": "🔵 Claude Haiku (~$0.001/run)"
        }[x]
    )

    key_hints = {
        "gemini": ("Gemini API Key", "aistudio.google.com — free, no card"),
        "groq":   ("Groq API Key",   "console.groq.com — free, no card"),
        "claude": ("Claude API Key", "console.anthropic.com — starts sk-ant-"),
    }
    label, hint = key_hints[provider]
    ai_key = st.text_input(label, type="password", help=hint)

    # Show get-key link
    links = {
        "gemini": "https://aistudio.google.com/app/apikey",
        "groq":   "https://console.groq.com/keys",
        "claude": "https://console.anthropic.com/",
    }
    st.caption(f"[Get free API key →]({links[provider]})")

    anthropic_key = ai_key  # keep variable name for compatibility below

    if ai_key:
        try:
            init_client(ai_key, provider=provider)
            icons = {"gemini": "🟢", "groq": "🟡", "claude": "🔵"}
            st.success(f"{icons[provider]} {provider.title()} ready")
        except Exception as e:
            st.error(f"Init failed: {e}")

    st.markdown("---")

    # Drive setup (optional)
    use_drive = st.checkbox("Connect Google Drive for scripts", value=False)
    folder_id = ""
    drive_service = None

    if use_drive:
        st.info("Upload your service account JSON key below.")
        drive_key_file = st.file_uploader("Service Account JSON", type="json")
        folder_id = st.text_input(
            "Drive Folder ID",
            help="Last part of the folder URL: drive.google.com/drive/folders/THIS_PART"
        )
        if drive_key_file and folder_id:
            try:
                import json as _json
                from modules.drive import get_drive_service, list_scripts_in_folder
                creds_dict = _json.load(drive_key_file)
                drive_service = get_drive_service(creds_dict)
                available = list_scripts_in_folder(drive_service, folder_id)
                st.success(f"✓ {len(available)} scripts found in Drive")
                st.session_state.drive_available = available
                st.session_state.drive_service   = drive_service
            except Exception as e:
                st.error(f"Drive error: {e}")

    st.markdown("---")
    st.markdown("### 📁 Upload Master Excel")
    excel_file = st.file_uploader("Your complete tracker Excel", type=["xlsx", "xls"])

    if excel_file:
        try:
            df, warnings = load_and_aggregate(excel_file)
            st.session_state.df = df
            st.success(f"✓ {len(df)} unique scripts loaded")
            for w in warnings:
                st.markdown(f'<div class="warning-box">⚠️ {w}</div>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Excel error: {e}")

    st.markdown("---")

    # Manual script paste (fallback when Drive not connected)
    st.markdown("### 📝 Paste Scripts Manually")
    st.caption("Use this if Drive is not connected.")
    manual_code = st.text_input("Adset Code (e.g. GAI647)")
    manual_text = st.text_area("Paste script text here", height=120)
    if st.button("Add Script") and manual_code and manual_text:
        st.session_state.scripts[manual_code.strip()] = manual_text.strip()
        st.success(f"✓ {manual_code} added")

    if st.session_state.scripts:
        st.caption(f"Scripts loaded: {', '.join(st.session_state.scripts.keys())}")


# ── Main UI ──────────────────────────────────────────────────────────────────
st.markdown("# 🎬 Story Analyzer")
st.caption("Script performance analysis powered by Claude AI")

if st.session_state.df is None:
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color:#6b7280;">
      <div style="font-size:3rem; margin-bottom:12px;">📊</div>
      <div style="font-size:1.1rem; font-weight:600; color:#c4b5fd;">Upload your master Excel to begin</div>
      <div style="font-size:0.85rem; margin-top:8px;">
        Your Excel should include all columns: Writers, Adset Code, performance metrics, etc.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df = st.session_state.df
all_codes = get_available_adset_codes(df)

# ── Script selection ─────────────────────────────────────────────────────────
st.markdown("## 🎯 Select Scripts to Analyze")
col_sel, col_info = st.columns([3, 1])

with col_sel:
    selected_codes = st.multiselect(
        "Choose up to 4 Adset Codes",
        options=all_codes,
        max_selections=4,
        help="Each code corresponds to one script in your Drive"
    )

with col_info:
    if selected_codes:
        st.markdown(f"""
        <div class="metric-card">
          <div class="metric-val">{len(selected_codes)}</div>
          <div class="metric-label">Scripts Selected</div>
        </div>""", unsafe_allow_html=True)

# Show quick metrics for selected
if selected_codes:
    st.markdown("### 📋 Selected Scripts — Performance Snapshot")
    cols = st.columns(len(selected_codes))
    for i, code in enumerate(selected_codes):
        metrics = get_metrics_for_code(df, code)
        with cols[i]:
            thruplays = metrics.get("thruplays_pct", 0)
            ctr       = metrics.get("ctr", 0)
            cpi       = metrics.get("cost_per_result")
            spend     = metrics.get("spend_usd", 0)
            writer    = metrics.get("writers", "—")
            st.markdown(f"""
            <div style="background:#1e1b2e; border:1px solid #4c1d95; border-radius:10px; padding:12px;">
              <div style="font-size:0.9rem; font-weight:800; color:#a78bfa; margin-bottom:8px;">{code}</div>
              <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:6px;">✍️ {writer}</div>
              <div style="font-size:0.8rem; color:#e2e8f0;">ThruPlay: <b style="color:#22c55e">{thruplays:.1%}</b></div>
              <div style="font-size:0.8rem; color:#e2e8f0;">CTR: <b style="color:#60a5fa">{ctr:.2%}</b></div>
              <div style="font-size:0.8rem; color:#e2e8f0;">CPI: <b style="color:#fbbf24">${cpi:.2f}</b></div>
              <div style="font-size:0.8rem; color:#e2e8f0;">Spend: <b>${spend:.0f}</b></div>
            </div>""", unsafe_allow_html=True)

    # Script loading status
    st.markdown("### 📄 Script Files")
    script_cols = st.columns(len(selected_codes))
    for i, code in enumerate(selected_codes):
        with script_cols[i]:
            if code in st.session_state.scripts:
                char_count = len(st.session_state.scripts[code])
                st.success(f"✓ {code} ({char_count:,} chars)")
            elif use_drive and hasattr(st.session_state, "drive_available") and code in st.session_state.drive_available:
                if st.button(f"📥 Fetch {code}", key=f"fetch_{code}"):
                    with st.spinner(f"Fetching {code} from Drive..."):
                        try:
                            from modules.drive import extract_text_from_drive_file
                            file_id = st.session_state.drive_available[code]
                            text = extract_text_from_drive_file(
                                st.session_state.drive_service, file_id
                            )
                            st.session_state.scripts[code] = text
                            st.success(f"✓ {len(text):,} chars")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            else:
                st.warning(f"⚠️ {code}: paste script in sidebar")

    # ── Analyze button ────────────────────────────────────────────────────────
    st.markdown("---")
    ready_codes = [c for c in selected_codes if c in st.session_state.scripts]
    missing     = [c for c in selected_codes if c not in st.session_state.scripts]

    if missing:
        st.markdown(f'<div class="warning-box">⚠️ Missing scripts for: {", ".join(missing)}. Paste them in the sidebar or fetch from Drive.</div>', unsafe_allow_html=True)

    analyze_disabled = not anthropic_key or not ready_codes
    if st.button("🚀 Run Analysis", disabled=analyze_disabled, use_container_width=True):
        progress = st.progress(0, text="Starting analysis...")
        new_analyses = {}
        metrics_map  = {}

        for idx, code in enumerate(ready_codes):
            progress.progress((idx) / len(ready_codes), text=f"Analyzing {code}...")
            metrics = get_metrics_for_code(df, code)
            m_text  = metrics_summary_text(metrics)
            metrics_map[code] = m_text

            try:
                result = analyze_single(
                    script_text=st.session_state.scripts[code],
                    metrics_text=m_text,
                    adset_code=code
                )
                new_analyses[code] = result
            except Exception as e:
                st.error(f"Analysis failed for {code}: {e}")

        if len(new_analyses) > 1:
            progress.progress(0.9, text="Generating comparison...")
            try:
                comparison = compare_scripts(new_analyses, metrics_map)
                st.session_state.comparison = comparison
            except Exception as e:
                st.warning(f"Comparison failed: {e}")
                st.session_state.comparison = {}

        st.session_state.analyses = new_analyses
        progress.progress(1.0, text="Done!")
        st.rerun()


# ── Results ──────────────────────────────────────────────────────────────────
if st.session_state.analyses:
    st.markdown("---")
    st.markdown("## 📈 Analysis Results")

    tab_names = list(st.session_state.analyses.keys())
    if st.session_state.comparison:
        tab_names += ["🆚 Comparison"]

    tabs = st.tabs(tab_names)

    for i, code in enumerate(st.session_state.analyses.keys()):
        a       = st.session_state.analyses[code]
        metrics = get_metrics_for_code(df, code)

        with tabs[i]:
            # Header
            overall = a.get("overall_score", 0)
            col_h1, col_h2 = st.columns([3, 1])
            with col_h1:
                st.markdown(f"### {code}")
                writer = metrics.get("writers", "")
                if writer:
                    st.caption(f"✍️ Writer: {writer}")
                st.markdown(f'<div class="insight-card"><b>Verdict:</b> {a.get("verdict", "")}</div>', unsafe_allow_html=True)
            with col_h2:
                color = score_color(overall)
                st.markdown(f"""
                <div style="text-align:center; background:#1e1b2e; border:3px solid {color};
                     border-radius:12px; padding:16px; margin-top:4px;">
                  <div style="font-size:2.5rem; font-weight:900; color:{color}">{overall}</div>
                  <div style="font-size:0.7rem; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">Overall Score</div>
                  <div style="font-size:0.8rem; color:{color}; font-weight:700; margin-top:2px;">{score_label(overall)}</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # KPI row
            kpi_cols = st.columns(5)
            kpis = [
                ("ThruPlay %",  f"{metrics.get('thruplays_pct', 0):.1%}"),
                ("CTR %",       f"{metrics.get('ctr', 0):.2%}"),
                ("CPI (USD)",   f"${metrics.get('cost_per_result', 0):.2f}" if metrics.get('cost_per_result') else "—"),
                ("Installs",    str(int(metrics.get("results", 0))) if metrics.get("results") else "—"),
                ("Spend",       f"${metrics.get('spend_usd', 0):.0f}"),
            ]
            for j, (label, val) in enumerate(kpis):
                with kpi_cols[j]:
                    st.markdown(f"""
                    <div class="metric-card">
                      <div class="metric-val">{val}</div>
                      <div class="metric-label">{label}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")
            col_scores, col_funnel = st.columns([3, 2])

            with col_scores:
                st.markdown("### 🎯 Score Breakdown")
                render_score_row("Hook",          a.get("hook_score", 0),          a.get("hook_finding", ""),          a.get("hook_recommendation", ""))
                render_score_row("Pacing",         a.get("pacing_score", 0),        a.get("pacing_finding", ""),        a.get("pacing_recommendation", ""))
                render_score_row("Emotional Arc",  a.get("emotional_arc_score", 0), a.get("emotional_arc_finding", ""), a.get("emotional_arc_recommendation", ""))
                render_score_row("CTA",            a.get("cta_score", 0),           a.get("cta_finding", ""),           a.get("cta_recommendation", ""))

            with col_funnel:
                st.markdown("### 📉 Retention Funnel")
                render_retention_funnel(metrics)

            st.markdown("---")
            col_why, col_imp = st.columns(2)

            with col_why:
                st.markdown("### 🧠 Why It Performed")
                st.markdown(f'<div class="insight-card" style="font-size:0.85rem; line-height:1.7">{a.get("why_it_performed", "")}</div>', unsafe_allow_html=True)
                st.markdown("**Retention Correlation**")
                st.markdown(f'<div class="finding-row" style="font-size:0.82rem; line-height:1.6">{a.get("retention_correlation", "")}</div>', unsafe_allow_html=True)

            with col_imp:
                st.markdown("### ✅ Top 3 Improvements")
                for imp in a.get("top_3_improvements", []):
                    st.markdown(f'<div class="rec-row" style="font-size:0.83rem">→ {imp}</div>', unsafe_allow_html=True)
                st.markdown("**Writer Feedback**")
                st.markdown(f'<div class="insight-card" style="font-size:0.82rem; line-height:1.6; border-color:#7c3aed">{a.get("writer_feedback", "")}</div>', unsafe_allow_html=True)

    # ── Comparison tab ────────────────────────────────────────────────────────
    if st.session_state.comparison and len(tabs) > len(st.session_state.analyses):
        comp = st.session_state.comparison
        with tabs[-1]:
            st.markdown("### 🆚 Cross-Script Comparison")

            col_w, col_r = st.columns([2, 3])
            with col_w:
                winner = comp.get("winner", "")
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#065f46,#064e3b); border:2px solid #22c55e;
                     border-radius:12px; padding:20px; text-align:center; margin-bottom:12px;">
                  <div style="font-size:1.8rem;">🏆</div>
                  <div style="font-size:1.2rem; font-weight:900; color:#22c55e">{winner}</div>
                  <div style="font-size:0.8rem; color:#a7f3d0; margin-top:6px">{comp.get("winner_reason","")}</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("**Rankings**")
                for rank in comp.get("ranking", []):
                    st.markdown(f'<div class="finding-row"><b>{rank.get("code")}</b> — Score {rank.get("score")} — {rank.get("one_line","")}</div>', unsafe_allow_html=True)

            with col_r:
                st.markdown("**Radar Comparison**")
                render_radar(st.session_state.analyses)

            st.markdown("---")
            col_p, col_hw = st.columns(2)

            with col_p:
                st.markdown("**Pattern Insights**")
                st.markdown(f'<div class="insight-card" style="font-size:0.83rem; line-height:1.7">{comp.get("pattern_insights","")}</div>', unsafe_allow_html=True)
                st.markdown("**Hook Pattern**")
                st.markdown(f'<div class="finding-row" style="font-size:0.82rem">{comp.get("hook_pattern","")}</div>', unsafe_allow_html=True)
                st.markdown("**Writer Pattern**")
                st.markdown(f'<div class="finding-row" style="font-size:0.82rem">{comp.get("writer_pattern","")}</div>', unsafe_allow_html=True)

            with col_hw:
                st.markdown("**✅ What to Replicate**")
                for item in comp.get("what_to_replicate", []):
                    st.markdown(f'<div class="rec-row" style="font-size:0.82rem">→ {item}</div>', unsafe_allow_html=True)
                st.markdown("**❌ What to Avoid**")
                for item in comp.get("what_to_avoid", []):
                    st.markdown(f'<div class="finding-row" style="font-size:0.82rem; border-left-color:#ef4444">✗ {item}</div>', unsafe_allow_html=True)
                st.markdown("**🔬 Next Test Recommendation**")
                st.markdown(f'<div class="insight-card" style="font-size:0.83rem; border-color:#f59e0b">{comp.get("next_test_recommendation","")}</div>', unsafe_allow_html=True)

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("📥 Export Full Report (Excel)", use_container_width=False):
        xlsx_bytes = export_results(
            st.session_state.analyses,
            st.session_state.comparison,
            df
        )
        st.download_button(
            label="⬇️ Download Report",
            data=xlsx_bytes,
            file_name="story_analyzer_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

