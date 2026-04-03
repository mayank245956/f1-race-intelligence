"""pages/season_hub.py — F1 Intelligence v3"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.pipeline import current_standings, build_base, load_ergast, team_color


def render():
    st.title("🏆 Season Hub")
    raw = load_ergast()
    all_years = sorted(raw["races"]["year"].dropna().unique().astype(int), reverse=True)
    year = st.selectbox("Select Season", all_years, index=0)

    with st.spinner(f"Loading {year} standings..."):
        std = current_standings(year)

    drv = std["driver"]
    con = std["constructor"]

    if drv.empty:
        st.warning("No data for this season yet.")
        return

    races_yr  = raw["races"][raw["races"]["year"] == year]
    completed = races_yr[races_yr["raceId"].isin(raw["results"]["raceId"].unique())]

    m1,m2,m3,m4 = st.columns(4)
    leader = drv.iloc[0]
    m1.metric("🥇 Leader",          leader["driver_name"],  f"{int(leader['points'])} pts")
    m2.metric("🏁 Rounds Done",     f"{len(completed)} / {len(races_yr)}")
    if len(drv) > 1:
        gap = int(drv.iloc[0]["points"]) - int(drv.iloc[1]["points"])
        m3.metric("📏 Gap to P2",   f"{gap} pts")
    if not con.empty:
        m4.metric("🏗️ Constructor", con.iloc[0]["name"],    f"{int(con.iloc[0]['points'])} pts")

    st.divider()
    tab1,tab2,tab3,tab4 = st.tabs(
        ["📊 Standings","📈 Points Flow","🏗️ Constructors","🏁 Race Results"])

    # ── Tab 1: Driver standings ───────────────────────────────────────────
    with tab1:
        st.subheader("Driver Championship")
        fig = go.Figure(go.Bar(
            x=drv["points"].astype(float), y=drv["driver_name"], orientation="h",
            marker=dict(color=drv["points"].astype(float),
                        colorscale=[[0,"#1A1A2E"],[1,"#E8002D"]]),
            text=drv["points"].astype(int), textposition="outside"))
        fig.update_layout(height=max(420,len(drv)*30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), xaxis_title="Points",
            margin=dict(l=0,r=60,t=10,b=20))
        st.plotly_chart(fig, use_container_width=True)

        # Safe column selection — only show cols that exist
        want = ["position","driver_name","nationality","team","points","wins","podiums","races"]
        show = [c for c in want if c in drv.columns]
        st.dataframe(drv[show].rename(columns={
            "position":"Pos","driver_name":"Driver","nationality":"Nat","team":"Team",
            "points":"Pts","wins":"Wins","podiums":"Podiums","races":"Races"
        }), use_container_width=True, hide_index=True)

    # ── Tab 2: Points flow ────────────────────────────────────────────────
    with tab2:
        base_yr = build_base(min_year=year, max_year=year)
        if base_yr.empty:
            st.info("No race data yet.")
        else:
            # base already has 'round' — use directly, no re-merge
            flow = base_yr.sort_values(["driver_name","round"])
            flow["cum_pts"] = flow.groupby("driver_name")["points"].cumsum()
            top10  = drv.head(10)["driver_name"].tolist()
            flow10 = flow[flow["driver_name"].isin(top10)]
            fig_f  = go.Figure()
            for dn in top10:
                d  = flow10[flow10["driver_name"]==dn].sort_values("round")
                tn = drv[drv["driver_name"]==dn]["team"].values
                fig_f.add_trace(go.Scatter(x=d["round"], y=d["cum_pts"],
                    mode="lines+markers", name=dn,
                    line=dict(color=team_color(tn[0]) if len(tn) else "#888", width=2),
                    marker=dict(size=5)))
            fig_f.update_layout(title=f"{year} Cumulative Points — Top 10",
                xaxis_title="Round", yaxis_title="Points",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="v",x=1.01,y=1), height=500)
            st.plotly_chart(fig_f, use_container_width=True)

    # ── Tab 3: Constructor standings ──────────────────────────────────────
    with tab3:
        if con.empty:
            st.info("No constructor data.")
        else:
            fig_c = go.Figure(go.Bar(
                x=con["points"].astype(float), y=con["name"], orientation="h",
                marker_color=[team_color(t) for t in con["name"]],
                text=con["points"].astype(int), textposition="outside"))
            fig_c.update_layout(height=max(300,len(con)*40),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(autorange="reversed"), xaxis_title="Points",
                margin=dict(l=0,r=60,t=10,b=20))
            st.plotly_chart(fig_c, use_container_width=True)
            want_c = ["position","name","points","wins"]
            st.dataframe(con[[c for c in want_c if c in con.columns]].rename(columns={
                "position":"Pos","name":"Constructor","points":"Pts","wins":"Wins"
            }), use_container_width=True, hide_index=True)

    # ── Tab 4: Race results ───────────────────────────────────────────────
    with tab4:
        base = build_base(min_year=year, max_year=year)
        if base.empty:
            st.info("No race data.")
        else:
            # base has 'round' already — just add race name
            race_name_map = raw["races"][["raceId","name"]].rename(columns={"name":"race_name"})
            race_list = (base.merge(race_name_map, on="raceId", how="left")
                         [["raceId","race_name","round"]].drop_duplicates()
                         .sort_values("round"))
            opts    = dict(zip(race_list["race_name"].fillna("Unknown"), race_list["raceId"]))
            sel     = st.selectbox("Select Race", list(opts.keys()))
            rid     = opts[sel]
            rr      = base[base["raceId"]==rid].copy().sort_values("positionOrder")
            rr["grid_delta"] = (rr["grid"] - rr["positionOrder"]).fillna(0).astype(int)
            if not raw["status"].empty:
                rr = rr.merge(raw["status"][["statusId","status"]], on="statusId", how="left")
            want_r = ["positionOrder","driver_name","team","grid","grid_delta","points","laps","status"]
            st.dataframe(rr[[c for c in want_r if c in rr.columns]].rename(columns={
                "positionOrder":"Pos","driver_name":"Driver","team":"Team",
                "grid":"Grid","grid_delta":"±Pos","points":"Pts","laps":"Laps","status":"Status"
            }), use_container_width=True, hide_index=True)
