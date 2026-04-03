"""
F1 Intelligence Dashboard v3
Run: streamlit run app.py
"""
import streamlit as st
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="F1 Intelligence v3",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .stApp { background-color: #0a0a14; color: #f0f0f0; }
  [data-testid="stSidebar"] {
      background: linear-gradient(180deg,#0f0f1a 0%,#12122a 100%);
      border-right: 1px solid #E8002D44;
  }
  [data-testid="metric-container"] {
      background: linear-gradient(135deg,#1a1a2e,#12122a);
      border: 1px solid #2a2a4a; border-radius: 10px; padding: 14px;
  }
  h1,h2,h3 { color:#ffffff; }
  hr { border-color:#2a2a4a; }
  .stTabs [data-baseweb="tab-list"] { gap:4px; }
  .stTabs [data-baseweb="tab"] {
      background:#1a1a2e; border-radius:6px 6px 0 0; color:#aaa; padding:8px 18px;
  }
  .stTabs [aria-selected="true"] {
      background:#E8002D22; color:#E8002D; border-bottom:2px solid #E8002D;
  }
  div[data-testid="stDataFrame"] { border:1px solid #2a2a4a; border-radius:6px; }
  .stat-card {
      background:linear-gradient(135deg,#1a1a2e,#0f0f1a);
      border:1px solid #2a2a4a; border-radius:12px;
      padding:20px; text-align:center; height:110px;
  }
  .stat-card .val { font-size:2em; font-weight:700; color:#E8002D; }
  .stat-card .lbl { font-size:0.78em; color:#888; margin-top:4px; }
  .nav-card {
      background:linear-gradient(135deg,#1a1a2e,#12122a);
      border:1px solid #2a2a4a; border-radius:12px;
      padding:18px; margin-bottom:10px; min-height:90px;
  }
  .nav-card h4 { color:#E8002D; margin:0 0 6px; }
  .nav-card p  { color:#aaa; font-size:0.84em; margin:0; }
  .hero-banner {
      background: linear-gradient(135deg,#0f0f1a 0%,#1a0a0a 50%,#0a0f1a 100%);
      border: 1px solid #E8002D33; border-radius: 16px;
      padding: 36px 40px; margin-bottom: 28px;
  }
</style>
""", unsafe_allow_html=True)

PAGES = {
    "🏠  Home":                  "home",
    "🏆  Season Hub":            "season",
    "🧠  Strategy Intelligence": "strategy",
    "👤  Driver Deep Dive":      "driver",
    "🏗️  Constructor Dynasty":  "constructor",
    "🔬  Race Anatomy":          "race",
    "📜  Records & Stats":       "records",
    "📐  How It Works":          "howto",
}

with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:16px 0 8px'>
        <div style='font-size:2.4em'>🏎️</div>
        <h2 style='margin:4px 0;color:#E8002D;font-size:1.05em;letter-spacing:3px'>
            F1 INTELLIGENCE</h2>
        <p style='color:#555;font-size:0.7em;margin:0'>v3.0 · 1950–2026</p>
    </div>""", unsafe_allow_html=True)
    st.markdown("---")
    page_label = st.radio("", list(PAGES.keys()), label_visibility="collapsed")
    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.7em;color:#555;padding:4px;line-height:1.7'>
    📦 <b style='color:#888'>Data sources</b><br>
    · Ergast F1 Dataset (1950–2026)<br>
    · toUpperCase78/formula1-datasets<br>
    · 744K+ data points<br><br>
    ⚡ <b style='color:#888'>Live enrichment</b><br>
    · 2022–2026 season data<br>
    · Fetched from GitHub at runtime
    </div>""", unsafe_allow_html=True)

page_key = PAGES[page_label]

# ═══════════════════════════════════════════════════════
#  HOME PAGE
# ═══════════════════════════════════════════════════════
if page_key == "home":
    from utils.pipeline import current_standings, build_base, load_ergast, team_color
    import plotly.graph_objects as go

    raw = load_ergast()

    # ── Hero Banner ──────────────────────────────────────────────────────
    st.markdown("""
    <div class='hero-banner'>
      <div style='display:flex;align-items:center;gap:16px;margin-bottom:12px'>
        <span style='font-size:3em'>🏎️</span>
        <div>
          <h1 style='margin:0;font-size:2em;color:#fff'>F1 Race Intelligence</h1>
          <p style='margin:4px 0 0;color:#888;font-size:0.95em'>
            75 seasons · 1,171 races · 866 drivers · 744,000+ data points
          </p>
        </div>
      </div>
      <p style='color:#aaa;margin:0;font-size:0.9em'>
        Full analytics platform — live standings, tyre strategy models, driver head-to-head,
        era dominance tracking, all-time records and more.
      </p>
    </div>""", unsafe_allow_html=True)

    # ── All-Time Stats Bar ───────────────────────────────────────────────
    base = build_base(min_year=1950)
    career = base.groupby("driver_name").agg(
        wins =("positionOrder", lambda x:(x==1).sum()),
        races=("raceId","count"),
        points=("points","sum"),
    ).reset_index()
    top_wins   = career.nlargest(1,"wins").iloc[0]
    top_starts = career.nlargest(1,"races").iloc[0]
    top_pts    = career.nlargest(1,"points").iloc[0]
    total_races = raw["races"]["raceId"].nunique()
    total_drivers = raw["drivers"]["driverId"].nunique()
    total_seasons = raw["races"]["year"].nunique()

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    for col, val, lbl in [
        (c1, f"{int(top_wins['wins'])}", f"🏆 Most wins — {top_wins['driver_name']}"),
        (c2, f"{int(top_starts['races'])}", f"🏁 Most starts — {top_starts['driver_name']}"),
        (c3, f"{top_pts['points']:,.0f}", f"🔢 Most points — {top_pts['driver_name']}"),
        (c4, f"{total_races:,}", "📅 Total races"),
        (c5, f"{total_drivers}", "👤 Total drivers"),
        (c6, f"{total_seasons}", "📆 Seasons"),
    ]:
        col.markdown(f"""
        <div class='stat-card'>
          <div class='val'>{val}</div>
          <div class='lbl'>{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Live 2026 Standings ──────────────────────────────────────────────
    with st.spinner("Fetching 2026 live standings..."):
        std = current_standings(2026)

    if not std["driver"].empty:
        drv = std["driver"]
        con = std["constructor"]
        races_2026 = raw["races"][raw["races"]["year"]==2026]
        completed  = races_2026[races_2026["raceId"].isin(raw["results"]["raceId"].unique())]

        st.markdown(f"""
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
          <span style='font-size:1.4em'>⚡</span>
          <h2 style='margin:0;color:#fff'>2026 Season — Live Standings</h2>
          <span style='background:#E8002D22;color:#E8002D;border:1px solid #E8002D44;
                       border-radius:20px;padding:2px 12px;font-size:0.8em'>
            After {len(completed)} of {len(races_2026)} rounds
          </span>
        </div>""", unsafe_allow_html=True)

        cA,cB = st.columns(2)
        with cA:
            fig_d = go.Figure(go.Bar(
                x=drv["points"].fillna(0).astype(float),
                y=drv["driver_name"], orientation="h",
                marker=dict(color=drv["points"].fillna(0),
                            colorscale=[[0,"#1A1A2E"],[1,"#E8002D"]]),
                text=drv["points"].fillna(0).astype(int), textposition="outside"))
            fig_d.update_layout(title="Driver Championship",height=max(380, len(drv)*28),
                plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(autorange="reversed"),xaxis_title="Points",
                margin=dict(l=0,r=50,t=40,b=20))
            st.plotly_chart(fig_d, use_container_width=True)
        with cB:
            if not con.empty:
                fig_c = go.Figure(go.Bar(
                    x=con["points"].fillna(0).astype(float),
                    y=con["name"], orientation="h",
                    marker_color=[team_color(t) for t in con["name"]],
                    text=con["points"].fillna(0).astype(int), textposition="outside"))
                fig_c.update_layout(title="Constructor Championship",height=max(380, len(con)*36),
                    plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"),xaxis_title="Points",
                    margin=dict(l=0,r=50,t=40,b=20))
                st.plotly_chart(fig_c, use_container_width=True)

    st.divider()

    # ── Navigation Cards ─────────────────────────────────────────────────
    st.markdown("### 📌 Explore the Dashboard")
    r1,r2,r3,r4 = st.columns(4)
    cards = [
        (r1,"🏆 Season Hub",
         "Live championship standings, points flow chart, race-by-race results for any season."),
        (r1,"🧠 Strategy Intelligence",
         "Pit window optimiser, tyre degradation model, undercut analysis & pit crew benchmarks."),
        (r2,"👤 Driver Deep Dive",
         "Career arc, circuit heatmap, teammate H2H with year-by-year breakdown."),
        (r2,"🏗️ Constructor Dynasty",
         "Team dominance over eras, 5-year rolling wins, all drivers per constructor."),
        (r3,"🔬 Race Anatomy",
         "Positions gained/lost, lap times with smoothing, pit stop Gantt timeline."),
        (r3,"📜 Records & Stats",
         "All-time leaderboards, win streaks, youngest/oldest winners, nationality breakdown."),
        (r4,"📐 How It Works",
         "Data pipeline, degradation model math, undercut logic and tech stack explained."),
    ]
    for col,title,desc in cards:
        col.markdown(f"""
        <div class='nav-card'>
          <h4>{title}</h4>
          <p>{desc}</p>
        </div>""", unsafe_allow_html=True)

    st.info("👈 Use the sidebar to navigate between pages.")

# ═══════════════════════════════════════════════════════
#  PAGE ROUTING
# ═══════════════════════════════════════════════════════
elif page_key == "season":
    from pages.season_hub import render; render()

elif page_key == "strategy":
    from pages.strategy_intelligence import render; render()

elif page_key == "driver":
    from pages.driver_deep_dive import render; render()

elif page_key == "constructor":
    from pages.constructor_dynasty import render; render()

elif page_key == "race":
    from pages.race_anatomy import render; render()

elif page_key == "records":
    from pages.records import render; render()

elif page_key == "howto":
    from pages.how_it_works import render; render()
