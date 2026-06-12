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
GROUP_STAGE = "First Stage"
KNOCKOUT_STAGES = {"Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final"}

CACHE_TTL_SECONDS = 90
_cache = {"timestamp": 0, "standings": None, "error": None}


def fetch_matches():
    req = urllib.request.Request(FIFA_MATCHES_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("Results", [])


def compute_eliminations(matches):
    """Returns the set of team codes that are eliminated from the tournament.

    Group stage: a team is eliminated once its group is fully played and it
    finishes 4th, or finishes 3rd but isn't among the 8 best 3rd-place teams
    across all groups (only checked once all 12 groups are complete).
    Knockout stage: a team is eliminated as soon as it loses a match.
    """
    eliminated = set()

    group_matches = {}
    group_teams = {}
    for m in matches:
        stage = m.get("StageName", [{}])[0].get("Description")
        if stage != GROUP_STAGE:
            continue
        home, away = m.get("Home") or {}, m.get("Away") or {}
        if not home.get("IdCountry") or not away.get("IdCountry"):
            continue
        gid = m.get("IdGroup")
        group_matches.setdefault(gid, []).append(m)
        group_teams.setdefault(gid, set())
        group_teams[gid].add(home["IdCountry"])
        group_teams[gid].add(away["IdCountry"])

    third_place_candidates = []
    groups_complete = 0
    for gid, gms in group_matches.items():
        teams = group_teams[gid]
        if len(teams) != 4:
            continue
        finished = [m for m in gms if m.get("MatchStatus") == 0]
        if len(finished) != 6:  # round-robin of 4 teams = 6 matches
            continue
        groups_complete += 1

        stats = {code: {"pts": 0, "gd": 0, "gs": 0} for code in teams}
        for m in finished:
            home, away = m["Home"], m["Away"]
            hs, aw = m["HomeTeamScore"], m["AwayTeamScore"]
            hc, ac = home["IdCountry"], away["IdCountry"]
            stats[hc]["gs"] += hs
            stats[hc]["gd"] += hs - aw
            stats[ac]["gs"] += aw
            stats[ac]["gd"] += aw - hs
            if hs > aw:
                stats[hc]["pts"] += 3
            elif aw > hs:
                stats[ac]["pts"] += 3
            else:
                stats[hc]["pts"] += 1
                stats[ac]["pts"] += 1

        ranked = sorted(
            stats.items(),
            key=lambda kv: (-kv[1]["pts"], -kv[1]["gd"], -kv[1]["gs"]),
        )
        eliminated.add(ranked[3][0])  # 4th place is always out
        code, third_stats = ranked[2]
        third_place_candidates.append((code, third_stats["pts"], third_stats["gd"], third_stats["gs"]))

    if groups_complete == 12 and len(third_place_candidates) == 12:
        ranked_thirds = sorted(third_place_candidates, key=lambda t: (-t[1], -t[2], -t[3]))
        for code, *_ in ranked_thirds[8:]:
            eliminated.add(code)

    for m in matches:
        stage = m.get("StageName", [{}])[0].get("Description")
        if stage not in KNOCKOUT_STAGES:
            continue
        if m.get("MatchStatus") != 0:
            continue
        winner_id = m.get("Winner")
        if not winner_id:
            continue
        for side in ("Home", "Away"):
            team = m.get(side, {})
            if team.get("IdCountry") and team.get("IdTeam") != winner_id:
                eliminated.add(team["IdCountry"])

    return eliminated


def build_team_schedules(matches):
    """Returns a dict of team code -> chronological list of all matches
    (played and upcoming) involving that team."""
    schedules = {code: [] for code in TEAMS}

    for m in matches:
        home, away = m.get("Home") or {}, m.get("Away") or {}
        home_code, away_code = home.get("IdCountry"), away.get("IdCountry")
        stage = m.get("StageName", [{}])[0].get("Description")
        finished = m.get("MatchStatus") == 0
        home_score, away_score = m.get("HomeTeamScore"), m.get("AwayTeamScore")

        for code, opponent_code, own_score, opp_score in (
            (home_code, away_code, home_score, away_score),
            (away_code, home_code, away_score, home_score),
        ):
            if code not in schedules:
                continue
            has_score = finished and own_score is not None and opp_score is not None
            result = None
            if has_score:
                if own_score > opp_score:
                    result = "w"
                elif own_score < opp_score:
                    result = "l"
                else:
                    result = "t"

            schedules[code].append({
                "date": m.get("Date"),
                "stage": stage,
                "opponent": opponent_code,
                "opponentName": TEAMS.get(opponent_code, {}).get("name", opponent_code or "TBD"),
                "opponentFlag": TEAMS.get(opponent_code, {}).get("flag", ""),
                "finished": finished,
                "score": f"{own_score}-{opp_score}" if has_score else None,
                "result": result,
            })

    for code in schedules:
        schedules[code].sort(key=lambda x: x["date"] or "")

    return schedules


def compute_standings(matches):
    eliminated_teams = compute_eliminations(matches)
    schedules = build_team_schedules(matches)

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

        home = m.get("Home") or {}
        away = m.get("Away") or {}
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
                "eliminated": code in eliminated_teams,
                "schedule": schedules[code],
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
