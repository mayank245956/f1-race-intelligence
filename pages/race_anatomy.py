"""pages/race_anatomy.py"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.pipeline import build_base, load_ergast, team_color


def render():
    st.title("🔬 Race Anatomy")
    raw = load_ergast()

    all_years = sorted(raw["races"]["year"].dropna().unique().astype(int), reverse=True)
    col1,col2 = st.columns(2)
    year = col1.selectbox("Season", all_years, index=0)

    completed_ids = set(raw["results"]["raceId"].unique())
    yr_races = (raw["races"][raw["races"]["year"]==year]
                .pipe(lambda df: df[df["raceId"].isin(completed_ids)])
                .sort_values("round"))

    if yr_races.empty:
        col2.write("")
        st.warning("No completed races for this season.")
        return

    race_opts = dict(zip(yr_races["name"], yr_races["raceId"]))
    sel_race  = col2.selectbox("Race", list(race_opts.keys()))
    rid       = race_opts[sel_race]

    base     = build_base(min_year=year, max_year=year)
    race_res = base[base["raceId"]==rid].copy()
    if race_res.empty:
        st.warning("No data for this race.")
        return

    race_res["grid_delta"] = (race_res["grid"] - race_res["positionOrder"]).fillna(0).astype(int)
    if not raw["status"].empty:
        race_res = race_res.merge(raw["status"][["statusId","status"]], on="statusId", how="left")
    else:
        race_res["status"] = "—"

    tab1,tab2,tab3,tab4 = st.tabs(["🏁 Results","📊 Positions Gained","⏱️ Lap Times","🛞 Pit Stops"])

    with tab1:
        want = ["positionOrder","driver_name","team","grid","grid_delta","points","laps","status"]
        st.dataframe(race_res.sort_values("positionOrder")[[c for c in want if c in race_res.columns]]
            .rename(columns={"positionOrder":"Pos","driver_name":"Driver","team":"Team",
                "grid":"Grid","grid_delta":"±Pos","points":"Pts","laps":"Laps","status":"Status"}),
            use_container_width=True, hide_index=True)

    with tab2:
        s = race_res.sort_values("positionOrder")
        fig = go.Figure(go.Bar(x=s["grid_delta"], y=s["driver_name"], orientation="h",
            marker_color=s["grid_delta"].apply(
                lambda v: "#00C851" if v>0 else("#E8002D" if v<0 else "#888")),
            text=s["grid_delta"], textposition="outside"))
        fig.update_layout(title="Positions Gained / Lost vs Grid",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), xaxis_title="Δ Position",
            height=max(400,len(race_res)*26), margin=dict(l=0,r=60,t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        if raw["lap_times"].empty:
            st.info("Lap time data not available.")
        else:
            lt = raw["lap_times"][raw["lap_times"]["raceId"]==rid].copy()
            lt = lt.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            lt["driver_name"]  = lt["forename"] + " " + lt["surname"]
            lt["milliseconds"] = pd.to_numeric(lt["milliseconds"], errors="coerce")
            lt["lap"]          = pd.to_numeric(lt["lap"],          errors="coerce")
            lt = lt.dropna(subset=["milliseconds"])
            lt["seconds"] = lt["milliseconds"] / 1000
            if lt.empty:
                st.info("No lap time data for this race.")
            else:
                top_drv = race_res.sort_values("positionOrder").head(10)["driver_name"].tolist()
                lt_top  = lt[lt["driver_name"].isin(top_drv)]
                smooth  = st.slider("Rolling smoothing (laps)",1,10,3)
                fig_lt  = go.Figure()
                for d in top_drv:
                    dd = lt_top[lt_top["driver_name"]==d].sort_values("lap")
                    tn = race_res[race_res["driver_name"]==d]["team"].values
                    fig_lt.add_trace(go.Scatter(x=dd["lap"],
                        y=dd["seconds"].rolling(smooth,min_periods=1).mean(),
                        name=d, mode="lines",
                        line=dict(color=team_color(tn[0]) if len(tn) else "#888",width=1.5)))
                fig_lt.update_layout(title="Lap Times (smoothed)",
                    xaxis_title="Lap", yaxis_title="Seconds",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=450)
                st.plotly_chart(fig_lt, use_container_width=True)
                st.subheader("Fastest Laps")
                fl = lt.loc[lt.groupby("driver_name")["seconds"].idxmin()][["driver_name","lap","seconds"]]
                fl = fl.sort_values("seconds").reset_index(drop=True)
                fl.insert(0,"Rank",range(1,len(fl)+1))
                fl["Time"] = fl["seconds"].apply(
                    lambda s: f"{int(s//60)}:{s%60:06.3f}" if pd.notna(s) else "—")
                st.dataframe(fl[["Rank","driver_name","lap","Time"]].rename(columns={
                    "driver_name":"Driver","lap":"Lap"}), use_container_width=True, hide_index=True)

    with tab4:
        if raw["pit_stops"].empty:
            st.info("Pit stop data not available.")
        else:
            ps = raw["pit_stops"][raw["pit_stops"]["raceId"]==rid].copy()
            ps = ps.merge(raw["drivers"][["driverId","forename","surname"]], on="driverId", how="left")
            ps["driver_name"]  = ps["forename"] + " " + ps["surname"]
            ps["milliseconds"] = pd.to_numeric(ps["milliseconds"], errors="coerce")
            ps["lap"]          = pd.to_numeric(ps["lap"],          errors="coerce")
            ps["duration_s"]   = ps["milliseconds"] / 1000
            if ps.empty:
                st.info("No pit stop data for this race.")
            else:
                ordered = race_res.sort_values("positionOrder")["driver_name"].tolist()
                ps_ord  = ps[ps["driver_name"].isin(ordered)]
                fig_ps  = go.Figure()
                for d in ordered:
                    dd = ps_ord[ps_ord["driver_name"]==d]
                    tn = race_res[race_res["driver_name"]==d]["team"].values
                    fig_ps.add_trace(go.Scatter(x=dd["lap"], y=[d]*len(dd), mode="markers",
                        marker=dict(size=dd["duration_s"].fillna(3).clip(upper=15)*3+5,
                                    color=team_color(tn[0]) if len(tn) else "#888",
                                    opacity=0.85, line=dict(width=1,color="#fff")),
                        name=d, text=dd["duration_s"].apply(
                            lambda s: f"{s:.2f}s" if pd.notna(s) else ""),
                        hovertemplate="%{y} Lap %{x}: %{text}<extra></extra>"))
                fig_ps.update_layout(title="Pit Stop Timeline",
                    xaxis_title="Lap", yaxis_title="Driver",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False, height=max(400,len(ordered)*22))
                st.plotly_chart(fig_ps, use_container_width=True)
                st.dataframe(ps[["driver_name","stop","lap","duration_s"]]
                    .sort_values(["driver_name","stop"])
                    .rename(columns={"driver_name":"Driver","stop":"Stop #",
                                     "lap":"Lap","duration_s":"Duration (s)"}),
                    use_container_width=True, hide_index=True)
