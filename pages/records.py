"""pages/records.py"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from utils.pipeline import build_base, load_ergast, team_color


def render():
    st.title("📜 Records & All-Time Stats")
    raw  = load_ergast()
    base = build_base()

    career = base.groupby("driver_name").agg(
        wins   =("positionOrder", lambda x: (x==1).sum()),
        podiums=("positionOrder", lambda x: (x<=3).sum()),
        points =("points",        "sum"),
        races  =("raceId",        "count"),
        seasons=("year",          "nunique"),
    ).reset_index()
    career["win_rate"] = (career["wins"] / career["races"].replace(0,np.nan)*100).round(1)

    if not raw["qualifying"].empty:
        q = raw["qualifying"].copy()
        q["position"] = pd.to_numeric(q["position"], errors="coerce")
        poles_id = q[q["position"]==1].groupby("driverId").size().reset_index(name="poles")
        drv_name_map = raw["drivers"][["driverId","forename","surname"]].copy()
        drv_name_map["driver_name"] = drv_name_map["forename"] + " " + drv_name_map["surname"]
        poles_named = poles_id.merge(drv_name_map[["driverId","driver_name"]], on="driverId")
        career = career.merge(poles_named[["driver_name","poles"]], on="driver_name", how="left")
        career["poles"] = career["poles"].fillna(0).astype(int)
    else:
        career["poles"] = 0

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏆 Leaderboards","🔥 Win Streaks","👶 Age Records","🌍 Nationality","⏳ Patient Winners"
    ])

    with tab1:
        metric = st.radio("Rank by",["wins","podiums","poles","points","races","win_rate"],horizontal=True)
        top_n  = st.slider("Top N", 5, 50, 20)
        df_s = career.sort_values(metric, ascending=False).head(top_n).reset_index(drop=True)
        df_s.insert(0,"rank",range(1,len(df_s)+1))
        fig = go.Figure(go.Bar(
            x=df_s[metric], y=df_s["driver_name"], orientation="h",
            marker=dict(color=df_s[metric], colorscale=[[0,"#1A1A2E"],[1,"#E8002D"]]),
            text=df_s[metric].apply(lambda v: f"{v:.1f}" if isinstance(v,float) else str(int(v))),
            textposition="outside"))
        fig.update_layout(title=f"All-Time Top {top_n} — {metric.replace('_',' ').title()}",
            height=max(400,top_n*26), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), margin=dict(l=0,r=80,t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)
        want = ["rank","driver_name","wins","podiums","poles","points","races","win_rate"]
        st.dataframe(df_s[[c for c in want if c in df_s.columns]].rename(columns={
            "rank":"#","driver_name":"Driver","wins":"Wins","podiums":"Podiums",
            "poles":"Poles","points":"Points","races":"Races","win_rate":"Win%"
        }), use_container_width=True, hide_index=True)

    with tab2:
        race_dates = raw["races"][["raceId","date"]].copy()
        race_dates["date"] = pd.to_datetime(race_dates["date"], errors="coerce")
        res_s = base.merge(race_dates, on="raceId", how="left").sort_values("date").reset_index(drop=True)

        def max_streak(series):
            best = cur = 0
            for v in series:
                if v == 1: cur += 1; best = max(best, cur)
                else: cur = 0
            return best

        streaks = (res_s.groupby("driver_name")["positionOrder"]
                   .apply(max_streak).reset_index(name="max_streak")
                   .sort_values("max_streak", ascending=False).head(20).reset_index(drop=True))
        streaks.insert(0,"rank",range(1,len(streaks)+1))
        fig_s = go.Figure(go.Bar(x=streaks["max_streak"], y=streaks["driver_name"], orientation="h",
            marker_color="#E8002D", text=streaks["max_streak"], textposition="outside"))
        fig_s.update_layout(title="Longest Consecutive Win Streaks", height=500,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), margin=dict(l=0,r=60,t=40,b=20))
        st.plotly_chart(fig_s, use_container_width=True)
        st.dataframe(streaks.rename(columns={"rank":"#","driver_name":"Driver","max_streak":"Streak"}),
            use_container_width=True, hide_index=True)

    with tab3:
        # drivers.csv HAS dob and nationality columns (confirmed)
        race_dates2 = raw["races"][["raceId","date"]].copy()
        race_dates2["date"] = pd.to_datetime(race_dates2["date"], errors="coerce")

        drv_info = raw["drivers"][["driverId","forename","surname","dob","nationality"]].copy()
        drv_info["driver_name"] = drv_info["forename"] + " " + drv_info["surname"]
        drv_info["dob"] = pd.to_datetime(drv_info["dob"], errors="coerce")

        wins_only = base[base["positionOrder"]==1][["raceId","driver_name","driverId"]].copy()
        wins_df = (wins_only
                   .merge(race_dates2, on="raceId", how="left")
                   .merge(drv_info[["driverId","dob","nationality"]], on="driverId", how="left"))

        wins_df = wins_df.dropna(subset=["dob","date"])
        if wins_df.empty:
            st.info("No age data available.")
        else:
            wins_df["age_days"]  = (wins_df["date"] - wins_df["dob"]).dt.days
            wins_df["age_years"] = (wins_df["age_days"] / 365.25).round(1)
            c1,c2 = st.columns(2)
            with c1:
                st.subheader("🐣 Youngest Winners")
                y_df = (wins_df.sort_values("age_days")
                        .drop_duplicates("driver_name")
                        [["driver_name","date","age_years","nationality"]]
                        .head(15).reset_index(drop=True))
                y_df.insert(0,"#",range(1,len(y_df)+1))
                st.dataframe(y_df.rename(columns={"driver_name":"Driver","date":"Date",
                    "age_years":"Age","nationality":"Nat"}), use_container_width=True, hide_index=True)
            with c2:
                st.subheader("👴 Oldest Winners")
                o_df = (wins_df.sort_values("age_days", ascending=False)
                        .drop_duplicates("driver_name")
                        [["driver_name","date","age_years","nationality"]]
                        .head(15).reset_index(drop=True))
                o_df.insert(0,"#",range(1,len(o_df)+1))
                st.dataframe(o_df.rename(columns={"driver_name":"Driver","date":"Date",
                    "age_years":"Age","nationality":"Nat"}), use_container_width=True, hide_index=True)

    with tab4:
        nat = (base.groupby("nationality")
               .agg(drivers=("driver_name","nunique"),
                    wins   =("positionOrder", lambda x:(x==1).sum()),
                    races  =("raceId","count"))
               .reset_index().sort_values("wins", ascending=False))
        fig_n = px.bar(nat.head(20), x="nationality", y="wins", color="wins",
            color_continuous_scale="Reds", title="Wins by Nationality (top 20)")
        fig_n.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False, height=400)
        st.plotly_chart(fig_n, use_container_width=True)
        st.dataframe(nat.rename(columns={"nationality":"Nationality","drivers":"Drivers",
            "wins":"Wins","races":"Races"}), use_container_width=True, hide_index=True)

    with tab5:
        race_dates3 = raw["races"][["raceId","date"]].copy()
        race_dates3["date"] = pd.to_datetime(race_dates3["date"], errors="coerce")
        base_d = base.merge(race_dates3, on="raceId", how="left")
        base_d["date"] = pd.to_datetime(base_d["date"], errors="coerce")

        def races_before_first_win(grp):
            grp = grp.sort_values("date")
            wins = grp[grp["positionOrder"]==1]
            if wins.empty: return None
            return int((grp["date"] < wins.iloc[0]["date"]).sum())

        patient = (base_d.groupby("driver_name")
                   .apply(races_before_first_win, include_groups=False)
                   .dropna().reset_index(name="races_before_win")
                   .sort_values("races_before_win", ascending=False)
                   .head(25).reset_index(drop=True))
        patient.insert(0,"#",range(1,len(patient)+1))
        fig_p = go.Figure(go.Bar(x=patient["races_before_win"], y=patient["driver_name"],
            orientation="h", marker_color="#FF8000",
            text=patient["races_before_win"], textposition="outside"))
        fig_p.update_layout(title="Most Races Before First Win", height=600,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(autorange="reversed"), margin=dict(l=0,r=60,t=40,b=20))
        st.plotly_chart(fig_p, use_container_width=True)
        st.dataframe(patient.rename(columns={"#":"#","driver_name":"Driver",
            "races_before_win":"Races Before 1st Win"}), use_container_width=True, hide_index=True)
