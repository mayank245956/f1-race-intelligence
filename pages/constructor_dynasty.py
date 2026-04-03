"""pages/constructor_dynasty.py"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.pipeline import build_base, load_ergast, team_color


def render():
    st.title("🏗️ Constructor Dynasty")
    raw  = load_ergast()
    base = build_base()

    con_career = base.groupby("team").agg(
        wins   =("positionOrder", lambda x:(x==1).sum()),
        races  =("raceId","count"),
        points =("points","sum"),
        seasons=("year","nunique"),
    ).reset_index().sort_values("wins", ascending=False).reset_index(drop=True)

    tab1,tab2,tab3,tab4 = st.tabs(
        ["🏆 All-Time Wins","📅 Season Dominance","📈 Rolling Era","🔍 Team Deep Dive"])

    with tab1:
        top_n = st.slider("Top N constructors",5,30,15)
        df_t  = con_career.head(top_n)
        fig = go.Figure(go.Bar(x=df_t["wins"], y=df_t["team"], orientation="h",
            marker_color=[team_color(t) for t in df_t["team"]],
            text=df_t["wins"], textposition="outside"))
        fig.update_layout(title="All-Time Constructor Wins", height=max(400,top_n*30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), xaxis_title="Wins",
            margin=dict(l=0,r=60,t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(con_career.head(top_n).rename(columns={
            "team":"Constructor","wins":"Wins","races":"Races",
            "points":"Points","seasons":"Seasons"}), use_container_width=True, hide_index=True)

    with tab2:
        sw = (base.groupby(["year","team"]).agg(
            wins=("positionOrder", lambda x:(x==1).sum()),
            pts =("points","sum")).reset_index())
        sw = sw[sw["wins"]>0]
        top_teams = con_career.head(12)["team"].tolist()
        sw = sw[sw["team"].isin(top_teams)]
        fig_b = go.Figure()
        for team in top_teams:
            td = sw[sw["team"]==team]
            if td.empty: continue
            fig_b.add_trace(go.Scatter(x=td["year"], y=td["wins"], mode="markers", name=team,
                marker=dict(size=td["wins"]*3+5, color=team_color(team), opacity=0.8,
                            line=dict(width=1,color="#fff")),
                text=td.apply(lambda r: f"{team}: {int(r['wins'])}W",axis=1),
                hovertemplate="%{text}<extra></extra>"))
        fig_b.update_layout(title="Season Wins by Constructor",
            xaxis_title="Year", yaxis_title="Wins in season",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=500)
        st.plotly_chart(fig_b, use_container_width=True)

    with tab3:
        pivot = (base.groupby(["year","team"])
                 .agg(wins=("positionOrder", lambda x:(x==1).sum()))
                 .reset_index().pivot(index="year",columns="team",values="wins")
                 .fillna(0).sort_index())
        rolling = pivot.rolling(5,min_periods=1).sum()
        top8 = con_career.head(8)["team"].tolist()
        fig_r = go.Figure()
        for team in top8:
            if team not in rolling.columns: continue
            fig_r.add_trace(go.Scatter(x=rolling.index, y=rolling[team], name=team,
                mode="lines", line=dict(color=team_color(team),width=2), stackgroup="one"))
        fig_r.update_layout(title="5-Year Rolling Win Share — Era transitions",
            xaxis_title="Year", yaxis_title="Wins (rolling 5yr)",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=450)
        st.plotly_chart(fig_r, use_container_width=True)

    with tab4:
        sel_team  = st.selectbox("Select Constructor", con_career["team"].tolist())
        team_data = base[base["team"]==sel_team]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Wins",    int((team_data["positionOrder"]==1).sum()))
        c2.metric("Races",   len(team_data))
        c3.metric("Drivers", team_data["driver_name"].nunique())
        c4.metric("Active",  f"{int(team_data['year'].min())} – {int(team_data['year'].max())}")
        yr_agg = team_data.groupby("year").agg(
            wins =("positionOrder", lambda x:(x==1).sum()),
            pts  =("points","sum"),
        ).reset_index()
        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(x=yr_agg["year"],y=yr_agg["wins"],
            name="Wins",marker_color=team_color(sel_team),opacity=0.8))
        fig_t.add_trace(go.Scatter(x=yr_agg["year"],y=yr_agg["pts"],
            name="Points",line=dict(color="#FFD700"),yaxis="y2"))
        fig_t.update_layout(title=f"{sel_team} — Season by Season",
            yaxis2=dict(overlaying="y",side="right",showgrid=False),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=380)
        st.plotly_chart(fig_t, use_container_width=True)
        st.subheader(f"All drivers for {sel_team}")
        drv_list = (team_data.groupby("driver_name").agg(
            races =("raceId","count"),
            wins  =("positionOrder", lambda x:(x==1).sum()),
            points=("points","sum"),
            first =("year","min"), last=("year","max"),
        ).reset_index().sort_values("races",ascending=False))
        st.dataframe(drv_list.rename(columns={"driver_name":"Driver","races":"Races",
            "wins":"Wins","points":"Points","first":"First","last":"Last"}),
            use_container_width=True, hide_index=True)
