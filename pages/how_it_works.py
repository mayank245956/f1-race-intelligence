"""pages/how_it_works.py"""
import streamlit as st
import plotly.graph_objects as go


def render():
    st.title("📐 How It Works")
    st.markdown("A technical breakdown of the data pipeline, models, and analysis methods used.")
    st.divider()

    st.subheader("🗄️ Data Architecture")
    st.markdown("""
The dashboard runs on **two data layers**:

**Layer 1 — Ergast F1 Dataset (1950–2026)**
A relational database of 14 CSV files covering every race, driver, constructor, lap time,
qualifying session and pit stop in F1 history. Loaded once and cached in memory.

**Layer 2 — Live GitHub Enrichment**
Race results and standings for 2022–2026 fetched at runtime from
[toUpperCase78/formula1-datasets](https://github.com/toUpperCase78/formula1-datasets).
Results are cached for 1 hour to avoid repeated downloads.
""")

    # Architecture diagram
    st.subheader("🔁 Data Flow")
    cols = st.columns(5)
    steps = [
        ("📁", "14 Ergast CSVs", "#1a1a2e"),
        ("⚙️", "pipeline.py\nbuild_base()", "#12122a"),
        ("🔗", "Merged DataFrame\n27,000+ rows", "#0f0f1a"),
        ("🌐", "Live GitHub\nEnrichment", "#12122a"),
        ("📊", "6 Dashboard\nPages", "#1a1a2e"),
    ]
    for col,(icon,label,bg) in zip(cols,steps):
        col.markdown(f"""
        <div style='background:{bg};border:1px solid #2a2a4a;border-radius:8px;
                    padding:16px;text-align:center;min-height:90px'>
            <div style='font-size:1.8em'>{icon}</div>
            <div style='font-size:0.8em;color:#ccc;margin-top:6px'>{label}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("🧠 Strategy Intelligence — Models")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("""
**Tyre Degradation Model**
Each stint is modelled with **linear regression** on lap time vs lap number:

`Lap_time(n) = base_time + slope × n`

- `slope` (ms/lap) = degradation rate
- Negative slope = driver improving / tyre warming
- Positive slope = classic rubber degradation

**Pit Window Optimiser**
Sweeps all possible pit laps (3 to N−3) and projects total race time:

`Total = Σstint₁ + Σstint₂ + pit_loss`

The lap that minimises projected time is the **optimal window**.
""")
    with c2:
        st.markdown("""
**Undercut Analysis**
Compares first pit lap timing to final position gain (grid → finish).
Drivers who pitted early and gained positions show undercut effectiveness.

**Head-to-Head (H2H)**
Only races where both drivers competed for the **same constructor** count.
Year-by-year breakdown shows dominance shifts over a shared career.

**Streak Detection**
All results are sorted chronologically per driver. A running counter
tracks consecutive wins — reset to 0 on any non-win.
""")

    st.divider()
    st.subheader("📦 Data Sources")
    st.markdown("""
| Source | Coverage | Used For |
|--------|----------|----------|
| Ergast F1 Dataset | 1950–2024 | All backbone analysis |
| toUpperCase78/formula1-datasets | 2019–2026 | Live season enrichment |
""")


    st.divider()
    st.subheader("⚠️ Model Limitations")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**Degradation Model**
- Uses linear regression — real tyre wear is non-linear
- R² of 0.05–0.25 is normal and expected (noisy racing data)
- Safety car laps, traffic, and fuel load changes increase noise
- IQR outlier removal helps but cannot eliminate all noise

**Pit Window Optimiser**
- Simulates 1-stop strategies only
- Assumes fixed 3% tyre gain on fresh rubber
- Does not model traffic, DRS, or undercut battles
- Pit loss (18–28s) varies by team — use slider to test sensitivity
""")
    with c2:
        st.markdown("""
**Undercut Analysis**
- Based on first pit lap vs final position — causality vs correlation
- Position gains can be from race incidents, not just strategy

**Head-to-Head**
- Only counts races at same constructor — guest appearances excluded
- Retirement-affected races still counted (may skew ratios)

**General**
- Ergast data ends at 2024; 2025–2026 from live GitHub fetch
- Live data may be incomplete mid-season
- Historical lap times only available from 2009 onwards
""")

    st.subheader("🛠️ Tech Stack")
    cols2 = st.columns(4)
    stack = [("🐍 Python 3.12","Core language"),
             ("📊 Streamlit","Web UI framework"),
             ("📈 Plotly","Interactive charts"),
             ("🐼 Pandas","Data processing")]
    for col,(name,desc) in zip(cols2,stack):
        col.markdown(f"""
        <div style='background:#1a1a2e;border:1px solid #2a2a4a;border-radius:8px;
                    padding:12px;text-align:center'>
            <b style='color:#E8002D'>{name}</b><br>
            <small style='color:#aaa'>{desc}</small>
        </div>""", unsafe_allow_html=True)
