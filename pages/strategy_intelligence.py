"""pages/strategy_intelligence.py — Real regression + simulation + optimization"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.pipeline import build_base, load_ergast, team_color


# ═══════════════════════════════════════════════════════
#  CORE MODELS
# ═══════════════════════════════════════════════════════

def _clean_laps(seconds: np.ndarray, iqr_multiplier: float = 1.5) -> np.ndarray:
    """Remove outliers (pit laps, safety car) using IQR method."""
    if len(seconds) < 4:
        return seconds
    q1, q3 = np.percentile(seconds, 25), np.percentile(seconds, 75)
    iqr = q3 - q1
    mask = (seconds >= q1 - iqr_multiplier*iqr) & (seconds <= q3 + iqr_multiplier*iqr)
    return seconds[mask]


def _fit_linear_degradation(lap_times_s: np.ndarray, lap_nums: np.ndarray):
    """
    Linear regression: lap_time = base + slope * lap_in_stint
    Returns (slope_ms_per_lap, base_lap_s, r2, n_clean)
    """
    if len(lap_times_s) < 3:
        return 0.0, float(np.mean(lap_times_s)) if len(lap_times_s) else 90.0, 0.0, 0

    # Clean outliers before fitting
    mask = np.ones(len(lap_times_s), dtype=bool)
    q1, q3 = np.percentile(lap_times_s, 25), np.percentile(lap_times_s, 75)
    iqr = q3 - q1
    mask = (lap_times_s >= q1 - 1.5*iqr) & (lap_times_s <= q3 + 1.5*iqr)
    y_clean = lap_times_s[mask]
    x_clean = lap_nums[mask]

    if len(y_clean) < 3:
        return 0.0, float(np.mean(lap_times_s)), 0.0, 0

    # OLS
    xm, ym = x_clean.mean(), y_clean.mean()
    denom = ((x_clean - xm)**2).sum()
    if denom < 1e-9:
        return 0.0, ym, 0.0, len(y_clean)

    slope = ((x_clean - xm) * (y_clean - ym)).sum() / denom
    intercept = ym - slope * xm

    y_hat  = slope * x_clean + intercept
    ss_res = ((y_clean - y_hat)**2).sum()
    ss_tot = ((y_clean - ym)**2).sum()
    r2     = float(1 - ss_res/ss_tot) if ss_tot > 1e-9 else 0.0
    r2     = max(0.0, min(1.0, r2))

    # slope in ms/lap, intercept in seconds
    return float(slope * 1000), float(intercept), r2, int(len(y_clean))


def _simulate_race(total_laps, pit_lap, slope1_ms, base1_s, slope2_ms, pit_loss_s):
    """
    Simulate 1-stop race total time for a given pit lap.
    Stint 1: laps 1…pit_lap   using degradation model 1
    Stint 2: laps 1…(total-pit) using degradation model 2 (fresh tyre = 3% faster base)
    """
    s1 = sum(base1_s + (slope1_ms/1000) * i for i in range(pit_lap))
    base2 = base1_s * 0.97      # fresh tyre base lap ~3% improvement
    slope2 = max(slope2_ms, slope1_ms * 0.5)  # fresh tyre degrades at least half rate
    s2 = sum(base2 + (slope2/1000) * i for i in range(total_laps - pit_lap))
    return s1 + s2 + pit_loss_s


def _format_time(total_s):
    """Format seconds as H:MM:SS.mmm"""
    h = int(total_s // 3600)
    m = int((total_s % 3600) // 60)
    s = total_s % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:06.3f}"
    return f"{m}:{s:06.3f}"


# ═══════════════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════════════

def render():
    st.title("🧠 Strategy Intelligence")
    st.markdown(
        "Pit window optimiser · Tyre degradation model · Undercut effectiveness · "
        "Pit crew benchmark — computed from 600K+ lap time records."
    )

    raw  = load_ergast()
    base = build_base()
    all_years = sorted(raw["races"]["year"].dropna().unique().astype(int), reverse=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Pit Window Optimiser", "📉 Degradation Benchmark",
        "🎯 Undercut Analysis",    "🔧 Pit Crew Speed"
    ])

    # ═══════════════════════════════════════════════════
    #  TAB 1 — PIT WINDOW OPTIMISER
    # ═══════════════════════════════════════════════════
    with tab1:
        st.subheader("Pit Window Optimiser")
        st.markdown(
            "The engine fits a **linear OLS regression** to each stint (outlier laps "
            "removed via IQR filter), then **simulates every possible pit lap** to find "
            "the minimum projected race time. The red dashed line = optimal; "
            "yellow = when the driver actually pitted."
        )

        c1, c2 = st.columns(2)
        year = c1.selectbox("Season", all_years, key="pw_year")
        completed_ids = set(raw["results"]["raceId"].unique())
        yr_races = (raw["races"][raw["races"]["year"]==year]
                    .pipe(lambda d: d[d["raceId"].isin(completed_ids)])
                    .sort_values("round"))
        race_opts = dict(zip(yr_races["name"], yr_races["raceId"]))
        sel_race  = c2.selectbox("Race", list(race_opts.keys()), key="pw_race")
        rid       = race_opts[sel_race]

        base_yr          = build_base(min_year=year, max_year=year)
        drivers_in_race  = sorted(base_yr[base_yr["raceId"]==rid]["driver_name"].unique())
        sel_drv          = st.selectbox("Driver", drivers_in_race, key="pw_drv")

        max_laps = int(base_yr[base_yr["raceId"]==rid]["laps"].max() or 58)
        col_a, col_b = st.columns(2)
        total_laps = col_a.slider("Total race laps", 30, 78, max_laps, key="pw_laps")
        pit_loss   = col_b.slider("Pit lane time loss (s)", 15.0, 35.0, 22.0, 0.5, key="pw_loss")

        if raw["lap_times"].empty:
            st.warning("⚠️ lap_times.csv required for this analysis.")
        else:
            lt = raw["lap_times"][raw["lap_times"]["raceId"]==rid].copy()
            lt = lt.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            lt["driver_name"] = lt["forename"] + " " + lt["surname"]
            lt["ms"]  = pd.to_numeric(lt["milliseconds"], errors="coerce")
            lt["lap"] = pd.to_numeric(lt["lap"],          errors="coerce")
            lt = lt.dropna(subset=["ms","lap"])
            lt["seconds"] = lt["ms"] / 1000
            drv_lt = lt[lt["driver_name"]==sel_drv].sort_values("lap").reset_index(drop=True)

            if drv_lt.empty:
                st.info(f"No lap data for {sel_drv} in this race.")
            else:
                # Get actual pit laps
                pit_laps = []
                if not raw["pit_stops"].empty:
                    ps = raw["pit_stops"][raw["pit_stops"]["raceId"]==rid].copy()
                    ps = ps.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
                    ps["driver_name"] = ps["forename"] + " " + ps["surname"]
                    ps["lap"] = pd.to_numeric(ps["lap"], errors="coerce")
                    pit_laps = sorted(ps[ps["driver_name"]==sel_drv]["lap"].dropna().astype(int).tolist())

                # Segment into stints
                boundaries = [0] + pit_laps + [int(drv_lt["lap"].max())+1]
                stints = []
                for i in range(len(boundaries)-1):
                    s = drv_lt[(drv_lt["lap"] > boundaries[i]) & (drv_lt["lap"] < boundaries[i+1])]
                    if not s.empty:
                        stints.append((int(s["lap"].min()), int(s["lap"].max()), s))

                # Fit degradation to each stint
                stint_models = []
                for (s_start, s_end, s_data) in stints:
                    laps_arr = s_data["lap"].values.astype(float)
                    time_arr = s_data["seconds"].values.astype(float)
                    # Normalize lap number within stint for better intercept
                    lap_in_stint = laps_arr - laps_arr[0]
                    sl, base_s, r2, n = _fit_linear_degradation(time_arr, lap_in_stint)
                    stint_models.append({
                        "start": s_start, "end": s_end,
                        "slope_ms": sl, "base_s": base_s,
                        "r2": r2, "n_clean": n, "data": s_data
                    })

                # Use stint 1 model for simulation
                m1 = stint_models[0] if stint_models else {"slope_ms":0,"base_s":90.0}
                m2 = stint_models[1] if len(stint_models)>1 else m1

                # Simulate all pit laps
                pit_range = list(range(3, total_laps-3))
                times = [_simulate_race(total_laps, pl,
                                        m1["slope_ms"], m1["base_s"],
                                        m2["slope_ms"], pit_loss)
                         for pl in pit_range]
                opt_idx  = int(np.argmin(times))
                opt_lap  = pit_range[opt_idx]
                opt_time = times[opt_idx]
                nostop   = sum(m1["base_s"] + (m1["slope_ms"]/1000)*i for i in range(total_laps))
                gain     = nostop - opt_time

                # ── Headline output ──────────────────────────────────────
                st.markdown("---")
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#1a0a0a,#0a0a1a);
                            border:1px solid #E8002D44;border-radius:12px;padding:20px;
                            margin-bottom:16px'>
                  <h3 style='color:#E8002D;margin:0 0 8px'>
                    ⚡ Recommendation: Pit on Lap {opt_lap} (±2 laps)
                  </h3>
                  <p style='color:#ccc;margin:0;font-size:0.95em'>
                    Projected race time improvement vs no-stop: 
                    <b style='color:#27F4D2'>+{gain:.1f}s</b> 
                    &nbsp;·&nbsp; Projected race time: 
                    <b style='color:#fff'>{_format_time(opt_time)}</b>
                    &nbsp;·&nbsp; Optimal window: Laps 
                    <b style='color:#FFD700'>{max(3,opt_lap-2)}–{min(total_laps-3,opt_lap+2)}</b>
                  </p>
                </div>""", unsafe_allow_html=True)

                m1c, m2c, m3c, m4c = st.columns(4)
                m1c.metric("⚡ Optimal pit lap", opt_lap)
                m2c.metric("📈 Gain vs no-stop", f"+{gain:.1f}s")
                actual = pit_laps[0] if pit_laps else None
                m3c.metric("🏁 Actual pit lap",  actual if actual else "—")
                if actual and 0 <= actual-3 < len(times):
                    delta = times[actual-3] - opt_time
                    m4c.metric("All stops", str(pit_laps),
                               f"+{delta:.1f}s vs optimal", delta_color="inverse")

                # ── Optimisation curve ───────────────────────────────────
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=pit_range, y=times,
                    mode="lines", line=dict(color="#27F4D2", width=2.5), name="Projected race time"))
                fig.add_vline(x=opt_lap, line=dict(color="#E8002D", dash="dash", width=2),
                    annotation_text=f"Optimal: Lap {opt_lap}", annotation_position="top left",
                    annotation_font_color="#E8002D")
                if actual:
                    fig.add_vline(x=actual, line=dict(color="#FFD700", dash="dot", width=1.5),
                        annotation_text=f"Actual: Lap {actual}", annotation_position="top right",
                        annotation_font_color="#FFD700")
                fig.add_vrect(x0=max(3,opt_lap-2), x1=min(total_laps-3,opt_lap+2),
                    fillcolor="#E8002D", opacity=0.1, line_width=0,
                    annotation_text="Optimal window ±2 laps", annotation_position="top left")
                fig.update_layout(
                    xaxis_title="Pit Lap", yaxis_title="Projected Total Race Time (s)",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=360)
                st.plotly_chart(fig, use_container_width=True)

                # ── Stint degradation models ─────────────────────────────
                st.subheader("Stint Degradation Models")
                st.caption(
                    "Linear OLS regression on cleaned lap times (IQR outlier removal). "
                    "Low R² is normal — lap times are noisy due to traffic, "
                    "safety cars and fuel load changes. The slope trend is what matters."
                )
                cols = st.columns(max(len(stint_models), 1))
                for i, sm in enumerate(stint_models):
                    with cols[i]:
                        color = "#00C851" if sm["slope_ms"] < 0 else "#E8002D"
                        trend = "📈 Improving" if sm["slope_ms"] < 0 else "📉 Degrading"
                        r2_rating = ("Good" if sm["r2"]>0.5 else
                                     "Moderate" if sm["r2"]>0.2 else "Low (noisy data)")
                        st.markdown(f"""
                        <div style='background:#1a1a2e;border:1px solid #2a2a4a;
                                    border-radius:10px;padding:16px;'>
                          <b>Stint {i+1} (Laps {sm['start']}–{sm['end']})</b><br>
                          <span style='font-size:2em;color:{color};font-weight:700'>
                            {sm['slope_ms']:+.1f} ms/lap
                          </span><br>
                          <small style='color:#888'>
                            Base lap: {sm['base_s']:.2f}s &nbsp;|&nbsp;
                            R²={sm['r2']:.2f} ({r2_rating}) &nbsp;|&nbsp;
                            {sm['n_clean']} clean laps used
                          </small><br>
                          <span style='color:#aaa;font-size:0.9em'>{trend}</span>
                        </div>""", unsafe_allow_html=True)

                # ── Degradation chart ────────────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                colors_a = ["#E8002D","#FF8000","#FFD700","#27F4D2"]
                colors_m = ["#ff6b6b","#ffa94d","#ffe066","#63e6be"]
                fig_d = go.Figure()
                for i, sm in enumerate(stint_models):
                    sd = sm["data"]
                    lap_in_s = sd["lap"].values - sd["lap"].values[0]
                    fig_d.add_trace(go.Scatter(x=sd["lap"].values, y=sd["seconds"].values,
                        mode="markers", name=f"Stint {i+1} actual",
                        marker=dict(color=colors_a[i%4], size=5, opacity=0.65)))
                    model_y = sm["base_s"] + (sm["slope_ms"]/1000) * np.arange(len(lap_in_s))
                    fig_d.add_trace(go.Scatter(x=sd["lap"].values, y=model_y,
                        mode="lines", name=f"Stint {i+1} model",
                        line=dict(color=colors_m[i%4], dash="dash", width=2)))
                fig_d.update_layout(
                    title="Actual vs Model Lap Times per Stint",
                    xaxis_title="Lap", yaxis_title="Lap Time (s)",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=380)
                st.plotly_chart(fig_d, use_container_width=True)

                # ── Model limitations ────────────────────────────────────
                with st.expander("⚠️ Model Limitations & Assumptions"):
                    st.markdown("""
**This model makes the following simplifications:**

1. **Linear degradation only** — Real tyre wear follows a non-linear curve
   (exponential in extreme cases). This model uses a straight-line approximation
   which works reasonably but can over/under-estimate late-stint degradation.

2. **Low R² is expected** — Lap times are inherently noisy due to traffic,
   safety car periods, fuel load changes and driver variance. R² of 0.05–0.25
   is normal. What matters is the **direction of the slope**, not the fit quality.

3. **Fixed tyre gain** — A 3% base lap time improvement on fresh tyres is assumed.
   Actual improvement depends on compound, track temperature and tyre warm-up.

4. **Single pit stop only** — The optimiser currently simulates 1-stop strategies.
   In high-degradation races, 2-stop may be faster — this is not modelled.

5. **No traffic or DRS modelling** — Undercuts and position battles that affect
   pace during out-laps are not captured.

6. **Static pit loss** — Real pit loss varies by team and track layout (18–28s).
   Use the slider to test sensitivity.

**Bottom line:** Use as a directional guide (±3 laps), not a precise prediction.
                    """)

    # ═══════════════════════════════════════════════════
    #  TAB 2 — DEGRADATION BENCHMARK
    # ═══════════════════════════════════════════════════
    with tab2:
        st.subheader("Tyre Degradation Benchmark")
        st.markdown("Compare degradation rates across all drivers in the same race. "
                    "Pit laps and safety car laps are removed via IQR filter before fitting.")

        c1, c2 = st.columns(2)
        year2   = c1.selectbox("Season", all_years, key="db_year")
        races2  = (raw["races"][raw["races"]["year"]==year2]
                   .pipe(lambda d: d[d["raceId"].isin(raw["results"]["raceId"])])
                   .sort_values("round"))
        opts2   = dict(zip(races2["name"], races2["raceId"]))
        sel2    = c2.selectbox("Race", list(opts2.keys()), key="db_race")
        rid2    = opts2[sel2]

        if raw["lap_times"].empty:
            st.info("Lap time data required.")
        else:
            lt2 = raw["lap_times"][raw["lap_times"]["raceId"]==rid2].copy()
            lt2 = lt2.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            lt2["driver_name"] = lt2["forename"] + " " + lt2["surname"]
            lt2["ms"]  = pd.to_numeric(lt2["milliseconds"], errors="coerce")
            lt2["lap"] = pd.to_numeric(lt2["lap"],          errors="coerce")
            lt2 = lt2.dropna(subset=["ms","lap"])
            lt2["seconds"] = lt2["ms"] / 1000

            deg_rows = []
            for drv_n, grp in lt2.groupby("driver_name"):
                if len(grp) < 8: continue
                laps_in_stint = (grp["lap"] - grp["lap"].min()).values.astype(float)
                times_arr     = grp["seconds"].values.astype(float)
                sl, bs, r2, n = _fit_linear_degradation(times_arr, laps_in_stint)
                deg_rows.append({
                    "Driver": drv_n,
                    "Deg (ms/lap)": round(sl, 1),
                    "Base Lap (s)": round(bs, 2),
                    "R²": round(r2, 2),
                    "Clean Laps": n
                })

            if deg_rows:
                deg_df = pd.DataFrame(deg_rows).sort_values("Deg (ms/lap)")
                fig_deg = go.Figure(go.Bar(
                    x=deg_df["Deg (ms/lap)"], y=deg_df["Driver"], orientation="h",
                    marker_color=deg_df["Deg (ms/lap)"].apply(
                        lambda v: "#00C851" if v < 0 else "#E8002D"),
                    text=deg_df["Deg (ms/lap)"].apply(lambda v: f"{v:+.1f}"),
                    textposition="outside"))
                fig_deg.update_layout(
                    title="Degradation Rate (lower/greener = better tyre management)",
                    xaxis_title="ms/lap (negative = improving pace)",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"), height=max(350, len(deg_df)*28))
                st.plotly_chart(fig_deg, use_container_width=True)
                st.dataframe(deg_df, use_container_width=True, hide_index=True)
                with st.expander("⚠️ Model Limitations"):
                    st.markdown("""
- All laps analysed as one stint — does not split by actual tyre age
- Low R² (< 0.3) is common; focus on relative ranking, not absolute values
- Safety car periods increase noise significantly
                    """)

    # ═══════════════════════════════════════════════════
    #  TAB 3 — UNDERCUT ANALYSIS
    # ═══════════════════════════════════════════════════
    with tab3:
        st.subheader("Undercut Effectiveness")
        st.markdown("Correlation between pit lap timing and final position gain.")

        c1, c2 = st.columns(2)
        year3  = c1.selectbox("Season", all_years, key="ua_year")
        races3 = (raw["races"][raw["races"]["year"]==year3]
                  .pipe(lambda d: d[d["raceId"].isin(raw["results"]["raceId"])])
                  .sort_values("round"))
        opts3  = dict(zip(races3["name"], races3["raceId"]))
        sel3   = c2.selectbox("Race", list(opts3.keys()), key="ua_race")
        rid3   = opts3[sel3]

        base3  = build_base(min_year=year3, max_year=year3)
        rr3    = base3[base3["raceId"]==rid3].sort_values("positionOrder")

        if raw["pit_stops"].empty:
            st.info("Pit stop data required.")
        else:
            ps3 = raw["pit_stops"][raw["pit_stops"]["raceId"]==rid3].copy()
            ps3 = ps3.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            ps3["driver_name"] = ps3["forename"] + " " + ps3["surname"]
            ps3["lap"] = pd.to_numeric(ps3["lap"], errors="coerce")
            fp = ps3.groupby("driver_name")["lap"].min().reset_index(name="first_pit_lap")
            rm = rr3[["driver_name","grid","positionOrder"]].merge(fp, on="driver_name", how="left")
            rm["pos_gain"] = rm["grid"] - rm["positionOrder"]
            rm = rm.dropna(subset=["first_pit_lap"]).sort_values("first_pit_lap")

            corr = rm[["first_pit_lap","pos_gain"]].corr().iloc[0,1]
            st.metric("Correlation: pit lap timing vs position gained", f"{corr:.2f}",
                      "Strong undercut effect" if abs(corr)>0.3 else "Weak undercut signal")

            fig_u = go.Figure()
            fig_u.add_trace(go.Scatter(
                x=rm["first_pit_lap"], y=rm["pos_gain"],
                mode="markers+text",
                text=rm["driver_name"].apply(lambda n: n.split()[-1]),
                textposition="top center",
                marker=dict(size=10, color=rm["pos_gain"],
                            colorscale="RdYlGn", showscale=True,
                            colorbar=dict(title="Pos gained"))))
            fig_u.add_hline(y=0, line=dict(color="#666", dash="dash"))
            fig_u.update_layout(title="First Pit Lap vs Positions Gained (green=gained, red=lost)",
                xaxis_title="First Pit Lap", yaxis_title="Positions Gained (grid→finish)",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=450)
            st.plotly_chart(fig_u, use_container_width=True)
            st.dataframe(rm[["driver_name","grid","positionOrder","first_pit_lap","pos_gain"]]
                .rename(columns={"driver_name":"Driver","grid":"Grid","positionOrder":"Finish",
                                  "first_pit_lap":"1st Pit Lap","pos_gain":"Pos Gained"}),
                use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════
    #  TAB 4 — PIT CREW SPEED
    # ═══════════════════════════════════════════════════
    with tab4:
        st.subheader("Pit Crew Speed Benchmark")
        c1, c2 = st.columns(2)
        year4  = c1.selectbox("Season", all_years, key="pc_year")
        races4 = (raw["races"][raw["races"]["year"]==year4]
                  .pipe(lambda d: d[d["raceId"].isin(raw["results"]["raceId"])])
                  .sort_values("round"))
        opts4  = dict(zip(races4["name"], races4["raceId"]))
        sel4   = c2.selectbox("Race", list(opts4.keys()), key="pc_race")
        rid4   = opts4[sel4]

        if raw["pit_stops"].empty:
            st.info("Pit stop data required.")
        else:
            ps4 = raw["pit_stops"][raw["pit_stops"]["raceId"]==rid4].copy()
            ps4 = ps4.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            ps4["driver_name"] = ps4["forename"] + " " + ps4["surname"]
            ps4 = ps4.merge(
                build_base(min_year=year4, max_year=year4)[["raceId","driver_name","team"]]
                .drop_duplicates(), on=["raceId","driver_name"], how="left")

            if "duration" in ps4.columns:
                ps4["dur_s"] = pd.to_numeric(ps4["duration"], errors="coerce")
            else:
                ps4["dur_s"] = pd.to_numeric(ps4["milliseconds"], errors="coerce") / 1000
            ps4 = ps4.dropna(subset=["dur_s"])
            ps4 = ps4[ps4["dur_s"].between(1.5, 60)]

            team_pit = (ps4.groupby("team")["dur_s"]
                        .agg(avg="mean", best="min", stops="count")
                        .reset_index().sort_values("avg"))

            fig_pit = go.Figure(go.Bar(
                x=team_pit["avg"], y=team_pit["team"], orientation="h",
                marker_color=[team_color(t) for t in team_pit["team"]],
                text=team_pit["avg"].apply(lambda v: f"{v:.2f}s"), textposition="outside"))
            fig_pit.update_layout(
                title="Average Pit Stop Duration by Constructor",
                xaxis_title="Duration (s)",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(autorange="reversed"), height=max(300, len(team_pit)*36))
            st.plotly_chart(fig_pit, use_container_width=True)
            st.dataframe(ps4[["driver_name","team","stop","lap","dur_s"]]
                .sort_values("dur_s")
                .rename(columns={"driver_name":"Driver","team":"Team",
                                  "stop":"Stop#","lap":"Lap","dur_s":"Duration (s)"}),
                use_container_width=True, hide_index=True)
