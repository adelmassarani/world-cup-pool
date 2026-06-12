import json
import time
import urllib.request

from data import PLAYERS, TEAMS, FIFA_COMPETITION_ID, FIFA_SEASON_ID

FIFA_MATCHES_URL = (
    "https://api.fifa.com/api/v3/calendar/matches"
    f"?idSeason={FIFA_SEASON_ID}&idCompetition={FIFA_COMPETITION_ID}"
    "&count=110&language=en"
)

EXCLUDED_STAGES = {"Play-off for third place"}

CACHE_TTL_SECONDS = 90
_cache = {"timestamp": 0, "standings": None, "error": None}


def fetch_matches():
    req = urllib.request.Request(FIFA_MATCHES_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("Results", [])


def compute_standings(matches):
    # Per-team record
    team_records = {
        code: {"w": 0, "l": 0, "t": 0, "results": []}
        for code in TEAMS
    }

    for m in matches:
        if m.get("MatchStatus") != 0:
            continue  # not finished yet
        stage = m.get("StageName", [{}])[0].get("Description")
        if stage in EXCLUDED_STAGES:
            continue

        home = m.get("Home", {})
        away = m.get("Away", {})
        home_code = home.get("IdCountry")
        away_code = away.get("IdCountry")
        home_score = m.get("HomeTeamScore")
        away_score = m.get("AwayTeamScore")

        if home_score is None or away_score is None:
            continue

        if home_score > away_score:
            outcome = {home_code: "w", away_code: "l"}
        elif away_score > home_score:
            outcome = {home_code: "l", away_code: "w"}
        else:
            outcome = {home_code: "t", away_code: "t"}

        for code, result in outcome.items():
            if code not in team_records:
                continue
            team_records[code][result] += 1
            opponent = away_code if code == home_code else home_code
            opp_score = away_score if code == home_code else home_score
            own_score = home_score if code == home_code else away_score
            team_records[code]["results"].append({
                "opponent": opponent,
                "opponentName": TEAMS.get(opponent, {}).get("name", opponent),
                "opponentFlag": TEAMS.get(opponent, {}).get("flag", ""),
                "score": f"{own_score}-{opp_score}",
                "result": result,
                "stage": stage,
                "date": m.get("Date"),
            })

    # Per-player totals
    players = []
    for name, codes in PLAYERS.items():
        total_w = total_l = total_t = 0
        squad = []
        for code in codes:
            rec = team_records[code]
            total_w += rec["w"]
            total_l += rec["l"]
            total_t += rec["t"]
            squad.append({
                "code": code,
                "name": TEAMS[code]["name"],
                "flag": TEAMS[code]["flag"],
                "w": rec["w"],
                "l": rec["l"],
                "t": rec["t"],
                "points": rec["w"] * 1 + rec["t"] * 0.5,
                "results": rec["results"],
            })
        points = total_w * 1 + total_t * 0.5
        players.append({
            "name": name,
            "points": points,
            "w": total_w,
            "l": total_l,
            "t": total_t,
            "squad": squad,
        })

    players.sort(key=lambda p: (-p["points"], -p["w"], p["name"]))
    return players


def get_standings(force=False):
    now = time.time()
    if not force and _cache["standings"] is not None and (now - _cache["timestamp"]) < CACHE_TTL_SECONDS:
        return _cache["standings"], _cache["error"], _cache["timestamp"]

    try:
        matches = fetch_matches()
        standings = compute_standings(matches)
        _cache["standings"] = standings
        _cache["error"] = None
        _cache["timestamp"] = now
    except Exception as e:
        _cache["error"] = str(e)
        if _cache["standings"] is None:
            _cache["standings"] = compute_standings([])
        _cache["timestamp"] = now

    return _cache["standings"], _cache["error"], _cache["timestamp"]
