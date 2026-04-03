"""pages/driver_deep_dive.py — with auto teammate detection"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.pipeline import build_base, load_ergast, team_color


def render():
    st.title("👤 Driver Deep Dive")
    raw  = load_ergast()
    base = build_base()

    drivers_list = sorted(base["driver_name"].dropna().unique())
    default = drivers_list.index("Lewis Hamilton") if "Lewis Hamilton" in drivers_list else 0
    driver  = st.selectbox("Select Driver", drivers_list, index=default)

    drv_data = base[base["driver_name"]==driver].copy()
    if drv_data.empty:
        st.warning("No data found.")
        return

    wins    = int((drv_data["positionOrder"]==1).sum())
    podiums = int((drv_data["positionOrder"]<=3).sum())
    races   = len(drv_data)
    points  = drv_data["points"].sum()
    seasons = drv_data["year"].nunique()
    teams   = drv_data["team"].dropna().unique()

    poles = 0
    if not raw["qualifying"].empty:
        q = raw["qualifying"].copy()
        q["position"] = pd.to_numeric(q["position"], errors="coerce")
        did_row = raw["drivers"][
            (raw["drivers"]["forename"]+" "+raw["drivers"]["surname"])==driver]
        if not did_row.empty:
            poles = int((q[q["driverId"]==did_row.iloc[0]["driverId"]]["position"]==1).sum())

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("🏆 Wins",   wins)
    c2.metric("🥇 Podiums",podiums)
    c3.metric("🎯 Poles",  poles)
    c4.metric("🏁 Races",  races)
    c5.metric("🔢 Points", f"{points:,.0f}")
    st.caption(f"**{seasons} seasons** · Teams: {', '.join(str(t) for t in teams if pd.notna(t))}")
    st.divider()

    tab1,tab2,tab3,tab4 = st.tabs(
        ["📈 Career Arc","🗺️ Circuit Heatmap","👥 Teammate H2H","📋 All Results"])

    with tab1:
        career = drv_data.groupby("year").agg(
            wins   =("positionOrder", lambda x:(x==1).sum()),
            points =("points","sum"),
            avg_fin=("positionOrder","mean"),
        ).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=career["year"],y=career["wins"],
            name="Wins",marker_color="#E8002D",opacity=0.7,yaxis="y1"))
        fig.add_trace(go.Scatter(x=career["year"],y=career["points"],
            name="Points",line=dict(color="#FFD700",width=2),yaxis="y2",mode="lines+markers"))
        fig.add_trace(go.Scatter(x=career["year"],y=career["avg_fin"],
            name="Avg Finish",line=dict(color="#64C4FF",width=2,dash="dot"),
            yaxis="y3",mode="lines+markers"))
        fig.update_layout(title=f"{driver} — Career Arc",
            plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",xaxis_title="Year",
            yaxis =dict(title="Wins",      side="left", showgrid=False),
            yaxis2=dict(title="Points",    side="right",overlaying="y",showgrid=False),
            yaxis3=dict(title="Avg Finish",side="right",overlaying="y",position=0.95,
                        showgrid=False,autorange="reversed"),
            legend=dict(orientation="h",y=-0.2),height=450)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if raw["circuits"].empty:
            race_info = raw["races"][["raceId","name"]].rename(columns={"name":"circuit"})
        else:
            circ = raw["circuits"][["circuitId","name"]].rename(columns={"name":"circuit"})
            race_info = raw["races"][["raceId","circuitId"]].merge(circ,on="circuitId")
        heat = drv_data.merge(race_info, on="raceId", how="left")
        heat_agg = heat.groupby("circuit").agg(
            races  =("raceId","count"),
            wins   =("positionOrder",lambda x:(x==1).sum()),
            avg_fin=("positionOrder","mean"),
        ).reset_index().sort_values("avg_fin")
        fig_h = px.bar(heat_agg.head(20),x="avg_fin",y="circuit",orientation="h",
            color="avg_fin",color_continuous_scale="RdYlGn_r",
            title=f"{driver} — Best circuits (avg finish)",
            text=heat_agg.head(20)["wins"].apply(lambda w:f"{int(w)}W" if w>0 else ""))
        fig_h.update_layout(plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",
            height=500,coloraxis_showscale=False)
        fig_h.update_traces(textposition="outside")
        st.plotly_chart(fig_h, use_container_width=True)

    with tab3:
        st.subheader("👥 Teammate Head-to-Head")

        # Find teammates: same constructor, same race, different driver
        # Use only raceId+team from drv_data to avoid year merge conflict
        drv_races = drv_data[["raceId","team","year"]].copy()

        same = (base[base["raceId"].isin(drv_races["raceId"]) & (base["driver_name"]!=driver)]
                .merge(drv_races.rename(columns={"team":"drv_team","year":"drv_year"}),
                       on="raceId", how="inner")
                .query("team==drv_team"))

        if same.empty:
            st.info("No teammate data found.")
        else:
            # Summary: how many races shared, which years
            tm_summary = (same.groupby("driver_name")
                          .agg(shared_races=("raceId","count"),
                               yr_min=("drv_year","min"),
                               yr_max=("drv_year","max"))
                          .reset_index()
                          .sort_values("shared_races", ascending=False))
            tm_summary["years"] = tm_summary.apply(
                lambda r: str(int(r["yr_min"])) if r["yr_min"]==r["yr_max"]
                          else f"{int(r['yr_min'])}–{int(r['yr_max'])}", axis=1)

            st.markdown("**Select a teammate** — years and race count shown automatically")
            tm_options = {
                f"{row['driver_name']}  ·  {row['years']}  ·  {row['shared_races']} races": row["driver_name"]
                for _, row in tm_summary.iterrows()
            }
            sel_label = st.selectbox("Teammate", list(tm_options.keys()))
            sel_tm    = tm_options[sel_label]

            tm_data = base[base["driver_name"]==sel_tm].copy()

            # H2H — only shared races, no year merge conflict
            shared = (drv_data[["raceId","positionOrder"]].rename(columns={"positionOrder":"pos_d"})
                      .merge(tm_data[["raceId","positionOrder"]].rename(columns={"positionOrder":"pos_t"}),
                             on="raceId")
                      .merge(drv_races[["raceId","year"]], on="raceId"))

            da  = int((shared["pos_d"]<shared["pos_t"]).sum())
            ta  = int((shared["pos_d"]>shared["pos_t"]).sum())
            tot = len(shared)

            s1,s2,s3 = st.columns(3)
            s1.metric(f"✅ {driver}", f"{da} races ahead", f"{da/max(tot,1)*100:.0f}%")
            s2.metric("🤝 Shared Races", tot)
            s3.metric(f"✅ {sel_tm}", f"{ta} races ahead", f"{ta/max(tot,1)*100:.0f}%")

            # Year-by-year bar
            yr_h2h = (shared.groupby("year")
                      .apply(lambda g: pd.Series({
                          driver:  int((g["pos_d"]<g["pos_t"]).sum()),
                          sel_tm:  int((g["pos_d"]>g["pos_t"]).sum()),
                          "Races": len(g)
                      }), include_groups=False)
                      .reset_index())

            fig_yr = go.Figure()
            fig_yr.add_trace(go.Bar(x=yr_h2h["year"],y=yr_h2h[driver],
                name=driver,marker_color="#E8002D",opacity=0.85))
            fig_yr.add_trace(go.Bar(x=yr_h2h["year"],y=yr_h2h[sel_tm],
                name=sel_tm,marker_color="#3671C6",opacity=0.85))
            fig_yr.update_layout(barmode="group",title="Head-to-Head per Year",
                xaxis_title="Year",yaxis_title="Races ahead of teammate",
                plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",
                height=320,legend=dict(orientation="h",y=-0.3))
            st.plotly_chart(fig_yr, use_container_width=True)

            # Scatter
            fig_sc = go.Figure()
            fig_sc.add_trace(go.Scatter(x=shared["pos_t"],y=shared["pos_d"],
                mode="markers",marker=dict(color="#E8002D",size=7,opacity=0.65)))
            fig_sc.add_trace(go.Scatter(x=[1,20],y=[1,20],mode="lines",
                line=dict(color="#555",dash="dash"),showlegend=False))
            fig_sc.update_layout(
                title=f"{driver} (y-axis) vs {sel_tm} (x-axis) — finish positions",
                xaxis_title=sel_tm,yaxis_title=driver,
                xaxis=dict(autorange="reversed"),yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)",height=400)
            st.plotly_chart(fig_sc, use_container_width=True)

            with st.expander("Year-by-year breakdown"):
                st.dataframe(yr_h2h.rename(columns={"year":"Year"}),
                             use_container_width=True, hide_index=True)

    with tab4:
        yr_min,yr_max = int(drv_data["year"].min()),int(drv_data["year"].max())
        y1,y2 = st.slider("Year range",yr_min,yr_max,(yr_min,yr_max))
        filtered = drv_data[(drv_data["year"]>=y1)&(drv_data["year"]<=y2)].copy()
        # base already has 'round' — just add race name
        race_name_map = raw["races"][["raceId","name"]].rename(columns={"name":"race_name"})
        filtered = filtered.merge(race_name_map, on="raceId", how="left")
        want = ["year","round","race_name","team","grid","positionOrder","points"]
        show = [c for c in want if c in filtered.columns]
        st.dataframe(filtered[show].sort_values(["year","round"]).rename(columns={
            "year":"Year","round":"Rd","race_name":"Race","team":"Team",
            "grid":"Grid","positionOrder":"Pos","points":"Pts"
        }), use_container_width=True, hide_index=True)
