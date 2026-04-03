"""
utils/pipeline.py — F1 Intelligence v2 data layer
Confirmed column names from actual Ergast CSVs:
  races:   raceId, year, round, circuitId, name, date
  drivers: driverId, forename, surname, dob, nationality
  results: raceId, driverId, constructorId, positionOrder, points, grid, laps, statusId
  constructors: constructorId, name, nationality
"""
import os, io, time, requests
from functools import lru_cache
import pandas as pd
import numpy as np

DATA_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
GITHUB_RAW = "https://raw.githubusercontent.com/toUpperCase78/formula1-datasets/master"

# ── Team colours ──────────────────────────────────────────────────────────────
TEAM_COLOURS = {
    "Red Bull": "#3671C6", "Ferrari": "#E8002D", "Mercedes": "#27F4D2",
    "McLaren": "#FF8000", "Aston Martin": "#358C75", "Alpine": "#FF87BC",
    "Williams": "#64C4FF", "RB": "#6692FF", "Haas": "#B6BABD",
    "Kick Sauber": "#52E252", "Sauber": "#52E252", "AlphaTauri": "#5E8FAA",
    "Alfa Romeo": "#C92D4B", "Racing Point": "#F596C8", "Renault": "#FFF500",
    "Toro Rosso": "#469BFF", "Force India": "#F596C8", "Lotus F1": "#FFB800",
    "Brawn": "#FFFB00", "Toyota": "#CC0000", "BMW Sauber": "#C0C0C0",
    "Cadillac": "#BA0C2F", "Jordan": "#FFD700", "BAR": "#C0C0C0",
    "Jaguar": "#006400", "Minardi": "#333333", "Arrows": "#FF7700",
    "Benetton": "#00AA00", "Brabham": "#006EAF", "Tyrrell": "#006EAF",
}

def team_color(name: str) -> str:
    for k, v in TEAM_COLOURS.items():
        if k.lower() in str(name).lower():
            return v
    return "#888888"


# ── Ergast loader ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_ergast() -> dict:
    files = {
        "races": "races.csv", "results": "results.csv", "drivers": "drivers.csv",
        "constructors": "constructors.csv", "qualifying": "qualifying.csv",
        "lap_times": "lap_times.csv", "pit_stops": "pit_stops.csv",
        "status": "status.csv", "driver_standings": "driver_standings.csv",
        "constructor_standings": "constructor_standings.csv",
        "constructor_results": "constructor_results.csv",
        "seasons": "seasons.csv", "sprint_results": "sprint_results.csv",
    }
    # circuits.csv may not exist
    raw = {}
    for key, fname in files.items():
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            try:
                raw[key] = pd.read_csv(path, na_values=["\\N", "N", ""])
            except Exception:
                raw[key] = pd.DataFrame()
        else:
            raw[key] = pd.DataFrame()

    # circuits — try loading, else empty
    circ_path = os.path.join(DATA_DIR, "circuits.csv")
    raw["circuits"] = pd.read_csv(circ_path) if os.path.exists(circ_path) else pd.DataFrame()

    # Ensure year is numeric in races
    if not raw["races"].empty:
        raw["races"]["year"] = pd.to_numeric(raw["races"]["year"], errors="coerce")

    return raw


# ── Build merged base frame ───────────────────────────────────────────────────
@lru_cache(maxsize=8)
def build_base(min_year: int = 1950, max_year: int = 2030) -> pd.DataFrame:
    raw = load_ergast()
    if raw["results"].empty or raw["races"].empty:
        return pd.DataFrame()

    res  = raw["results"].copy()
    race = raw["races"][["raceId","year","name","round","circuitId"]].copy()
    drv  = raw["drivers"][["driverId","forename","surname","nationality","dob"]].copy()
    drv["driver_name"] = drv["forename"] + " " + drv["surname"]
    con  = raw["constructors"][["constructorId","name"]].rename(columns={"name":"team"})

    base = (res
            .merge(race,                                      on="raceId",        how="left")
            .merge(drv[["driverId","driver_name","nationality","dob"]], on="driverId", how="left")
            .merge(con,                                       on="constructorId", how="left"))

    base["year"]          = pd.to_numeric(base["year"],         errors="coerce")
    base["positionOrder"] = pd.to_numeric(base["positionOrder"],errors="coerce")
    base["points"]        = pd.to_numeric(base["points"],       errors="coerce").fillna(0)
    base["grid"]          = pd.to_numeric(base["grid"],         errors="coerce")
    base["laps"]          = pd.to_numeric(base["laps"],         errors="coerce")

    base = base[(base["year"] >= min_year) & (base["year"] <= max_year)]
    return base.reset_index(drop=True)


# ── Live enrichment cache ─────────────────────────────────────────────────────
_cache, _cache_ts = {}, {}
_TTL = 3600

def _fetch_csv(url):
    now = time.time()
    if url in _cache and (now - _cache_ts.get(url, 0)) < _TTL:
        return _cache[url]
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            df = pd.read_csv(io.StringIO(r.text))
            _cache[url] = df; _cache_ts[url] = now
            return df
    except Exception:
        pass
    return None


# ── Current standings ─────────────────────────────────────────────────────────
def current_standings(year: int = 2026) -> dict:
    """Always returns dicts with keys: driver, constructor.
    driver columns: position, driver_name, nationality, team, points, wins, podiums, races
    constructor columns: position, name, points, wins
    """
    raw  = load_ergast()
    base = build_base(min_year=year, max_year=year)

    def _from_ergast():
        if base.empty:
            return pd.DataFrame(), pd.DataFrame()
        drv_grp = base.groupby("driver_name").agg(
            points     =("points",        "sum"),
            wins       =("positionOrder", lambda x: (x==1).sum()),
            podiums    =("positionOrder", lambda x: (x<=3).sum()),
            races      =("raceId",        "count"),
            team       =("team",          "last"),
            nationality=("nationality",   "first"),
        ).reset_index().sort_values("points", ascending=False).reset_index(drop=True)
        drv_grp.insert(0, "position", range(1, len(drv_grp)+1))

        con_grp = base.groupby("team").agg(
            points=("points",        "sum"),
            wins  =("positionOrder", lambda x: (x==1).sum()),
        ).reset_index().sort_values("points", ascending=False).reset_index(drop=True)
        con_grp.insert(0, "position", range(1, len(con_grp)+1))
        con_grp.rename(columns={"team":"name"}, inplace=True)
        return drv_grp, con_grp

    # Try live GitHub data
    for url_fmt in [
        f"{GITHUB_RAW}/Formula1_{year}Season_RaceResults.csv",
        f"{GITHUB_RAW}/formula1_{year}season_raceResults.csv",
    ]:
        live = _fetch_csv(url_fmt)
        if live is not None and not live.empty:
            col_lower = {c.lower().replace(" ","_"): c for c in live.columns}
            dc = col_lower.get("driver", col_lower.get("driver_name", col_lower.get("name")))
            tc = col_lower.get("team",   col_lower.get("constructor", col_lower.get("car")))
            pc = col_lower.get("points", col_lower.get("pts"))
            rc = col_lower.get("position", col_lower.get("pos"))

            if dc and pc and rc:
                live["_pts"] = pd.to_numeric(live[pc], errors="coerce").fillna(0)
                live["_pos"] = pd.to_numeric(live[rc], errors="coerce")

                drv_agg = live.groupby(dc).agg(
                    points =("_pts", "sum"),
                    wins   =("_pos", lambda x: (x==1).sum()),
                    podiums=("_pos", lambda x: (x<=3).sum()),
                    races  =("_pos", "count"),
                ).reset_index().rename(columns={dc:"driver_name"})

                if tc:
                    drv_agg["team"] = drv_agg["driver_name"].map(
                        live.groupby(dc)[tc].last().to_dict()).fillna("—")
                else:
                    drv_agg["team"] = "—"
                drv_agg["nationality"] = "—"
                drv_agg = drv_agg.sort_values("points", ascending=False).reset_index(drop=True)
                drv_agg.insert(0, "position", range(1, len(drv_agg)+1))

                con_agg = pd.DataFrame()
                if tc:
                    con_agg = live.groupby(tc).agg(
                        points=("_pts","sum"), wins=("_pos", lambda x:(x==1).sum())
                    ).reset_index().rename(columns={tc:"name"})
                    con_agg = con_agg.sort_values("points", ascending=False).reset_index(drop=True)
                    con_agg.insert(0, "position", range(1, len(con_agg)+1))

                return {"driver": drv_agg, "constructor": con_agg}

    drv_df, con_df = _from_ergast()
    return {"driver": drv_df, "constructor": con_df}
