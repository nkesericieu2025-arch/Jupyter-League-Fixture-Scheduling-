"""
Belgian Soccer League - simplified scheduling model (8 teams, mirrored double round-robin).

Implements the group's initial formulation (constraints 5-13) and adds:
  * wish type E  - "at most one top-vs-top match in round r" (integer violation)
  * lexicographic break minimization (stage 2)
  * a two-phase variant (fix home/away patterns first, then the matches)

All data are read from CSV files in data/.
"""
import csv
import time
from pathlib import Path

import pyomo.environ as pyo

N_ROUNDS = 14
HALF = 7
WISH_TYPES = {
    "A": "team i plays at home in round r",
    "B": "team i plays away in round r",
    "C": "teams i and j do not both play at home in round r",
    "D": "teams i and j do not meet in round r",
    "E": "at most one match between two top teams in round r",
}
H_ONLY_TYPES = {"A", "B", "C"}  # wishes that depend only on home/away status


# ----------------------------------------------------------------------------- data
def read_wish_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_data(data_dir="data", wish_files=("wishes_usecase.csv",), extra_rows=None):
    """Read teams, weights and wishes. A round value of 'all' expands to rounds 1..14."""
    d = Path(data_dir)
    with open(d / "teams.csv", newline="", encoding="utf-8") as f:
        teams = list(csv.DictReader(f))
    with open(d / "priority_weights.csv", newline="", encoding="utf-8") as f:
        weights = {int(r["level"]): float(r["penalty"]) for r in csv.DictReader(f)}

    rows = []
    for wf in wish_files:
        rows += read_wish_rows(d / wf if not Path(wf).is_absolute() else wf)
    rows += extra_rows or []

    codes = [t["code"] for t in teams]
    wishes = []
    for row in rows:
        t, lvl = row["type"].strip(), int(row["level"])
        i, j = (row.get("team_i") or "").strip() or None, (row.get("team_j") or "").strip() or None
        assert t in WISH_TYPES, f"{row['id']}: unknown type {t}"
        assert lvl in weights, f"{row['id']}: unknown level {lvl}"
        for team in (i, j):
            assert team is None or team in codes, f"{row['id']}: unknown team {team}"
        if t in "ABCD":
            assert i, f"{row['id']}: team_i required"
        if t in "CD":
            assert j and j != i, f"{row['id']}: team_j required and different from team_i"
        all_rounds = str(row["round"]).strip().lower() == "all"
        rounds = range(1, N_ROUNDS + 1) if all_rounds else [int(row["round"])]
        for r in rounds:
            assert 1 <= r <= N_ROUNDS, f"{row['id']}: round {r} out of range"
            wishes.append({
                "id": f"{row['id']}-r{r}" if all_rounds else row["id"],
                "rule": row["id"], "type": t, "level": lvl, "i": i, "j": j, "r": r,
                "stakeholder": row.get("stakeholder", ""),
                "description": row.get("description", ""),
                "group": row.get("conflict_group", ""),
            })
    return {
        "teams": codes,
        "names": {t["code"]: t["name"] for t in teams},
        "top": [t["code"] for t in teams if t["top"].strip() == "1"],
        "weights": weights,
        "wishes": wishes,
    }


# ---------------------------------------------------------------------------- model
def build_model(data, wishes=None, weights=None, fix_h=None):
    T = data["teams"]
    top = data["top"]
    W = data["wishes"] if wishes is None else wishes
    P = data["weights"] if weights is None else weights
    top_pairs = [(i, j) for i in top for j in top if i < j]

    m = pyo.ConcreteModel()
    m.T = pyo.Set(initialize=T, ordered=True)
    m.R = pyo.RangeSet(1, N_ROUNDS)
    m.R1 = pyo.RangeSet(1, HALF)
    m.RB = pyo.RangeSet(1, N_ROUNDS - 1)
    m.R3 = pyo.RangeSet(1, N_ROUNDS - 2)
    m.PAIRS = pyo.Set(initialize=[(i, j) for i in T for j in T if i != j], dimen=2)
    m.W = pyo.Set(initialize=range(len(W)))

    # (3) decision variables
    m.x = pyo.Var(m.PAIRS, m.R, within=pyo.Binary)      # x[i,j,r] = 1 if i hosts j in r
    m.h = pyo.Var(m.T, m.R, within=pyo.Binary)          # h[i,r] = 1 if i at home in r
    m.b = pyo.Var(m.T, m.RB, within=pyo.Binary)         # b[i,r] = 1 if break in r, r+1

    def v_bounds(m, w):
        return (0, len(top_pairs)) if W[w]["type"] == "E" else (0, 1)
    m.v = pyo.Var(m.W, within=pyo.NonNegativeIntegers, bounds=v_bounds)

    # (5) one match per team per round
    m.one_match = pyo.Constraint(m.T, m.R, rule=lambda m, i, r:
        sum(m.x[i, j, r] + m.x[j, i, r] for j in T if j != i) == 1)
    # (6) each pair meets once in the first half
    m.meet_once = pyo.Constraint([(i, j) for i in T for j in T if i < j], rule=lambda m, i, j:
        sum(m.x[i, j, r] + m.x[j, i, r] for r in m.R1) == 1)
    # (7) mirrored second half
    m.mirror = pyo.Constraint(m.PAIRS, m.R1, rule=lambda m, i, j, r:
        m.x[i, j, r + HALF] == m.x[j, i, r])
    # (8) link home status to matches
    m.home_link = pyo.Constraint(m.T, m.R, rule=lambda m, i, r:
        m.h[i, r] == sum(m.x[i, j, r] for j in T if j != i))
    # (9) no three consecutive home or away games
    m.max_two_lo = pyo.Constraint(m.T, m.R3, rule=lambda m, i, r:
        m.h[i, r] + m.h[i, r + 1] + m.h[i, r + 2] >= 1)
    m.max_two_hi = pyo.Constraint(m.T, m.R3, rule=lambda m, i, r:
        m.h[i, r] + m.h[i, r + 1] + m.h[i, r + 2] <= 2)
    # (10) identify breaks exactly
    m.brk1 = pyo.Constraint(m.T, m.RB, rule=lambda m, i, r: m.b[i, r] >= m.h[i, r] + m.h[i, r + 1] - 1)
    m.brk2 = pyo.Constraint(m.T, m.RB, rule=lambda m, i, r: m.b[i, r] >= 1 - m.h[i, r] - m.h[i, r + 1])
    m.brk3 = pyo.Constraint(m.T, m.RB, rule=lambda m, i, r: m.b[i, r] <= 1 + m.h[i, r] - m.h[i, r + 1])
    m.brk4 = pyo.Constraint(m.T, m.RB, rule=lambda m, i, r: m.b[i, r] <= 1 - m.h[i, r] + m.h[i, r + 1])
    # (11) no break at the start or end of the season
    m.no_start_break = pyo.Constraint(m.T, rule=lambda m, i: m.b[i, 1] == 0)
    m.no_end_break = pyo.Constraint(m.T, rule=lambda m, i: m.b[i, N_ROUNDS - 1] == 0)

    # (12) soft constraints: one per wish
    def wish_rule(m, w):
        k, i, j, r = W[w]["type"], W[w]["i"], W[w]["j"], W[w]["r"]
        if k == "A":
            return m.h[i, r] >= 1 - m.v[w]
        if k == "B":
            return m.h[i, r] <= m.v[w]
        if k == "C":
            return m.h[i, r] + m.h[j, r] <= 1 + m.v[w]
        if k == "D":
            return m.x[i, j, r] + m.x[j, i, r] <= m.v[w]
        if k == "E":
            return sum(m.x[a, c, r] + m.x[c, a, r] for a, c in top_pairs) <= 1 + m.v[w]
    m.wish = pyo.Constraint(m.W, rule=wish_rule)

    if fix_h:
        for (i, r), val in fix_h.items():
            m.h[i, r].fix(val)

    # (4) objective: weighted penalty of violated wishes
    m.penalty = pyo.Expression(expr=sum(P[W[w]["level"]] * m.v[w] for w in m.W))
    m.breaks = pyo.Expression(expr=sum(m.b[i, r] for i in m.T for r in m.RB))
    m.obj = pyo.Objective(expr=m.penalty, sense=pyo.minimize)
    m._wishes = W
    return m


# ---------------------------------------------------------------------------- solve
def _solve(m, time_limit):
    solver = pyo.SolverFactory("appsi_highs")
    solver.config.time_limit = time_limit
    res = solver.solve(m, load_solutions=False)
    status = str(res.solver.termination_condition)
    try:
        m.solutions.load_from(res)
        loaded = True
    except Exception:
        loaded = False
    return status, loaded


def solve(m, time_limit=60, min_breaks=True):
    """Stage 1: minimize penalty. Stage 2 (optional): fix penalty, minimize breaks."""
    t0 = time.time()
    s1, ok = _solve(m, time_limit)
    if not ok:
        return {"status": s1, "penalty": None, "breaks": None, "seconds": round(time.time() - t0, 1)}
    best = round(pyo.value(m.penalty))
    s2 = None
    if min_breaks:
        m.obj.deactivate()
        m.fix_penalty = pyo.Constraint(expr=m.penalty <= best + 1e-6)
        m.obj_breaks = pyo.Objective(expr=m.breaks, sense=pyo.minimize)
        s2, _ = _solve(m, time_limit)  # if no new solution loads, the stage-1 one stays
    return {
        "status": s1 if s2 is None else f"{s1} / breaks: {s2}",
        "penalty": round(pyo.value(m.penalty)),
        "breaks": round(pyo.value(m.breaks)),
        "seconds": round(time.time() - t0, 1),
    }


def solve_two_phase(data, time_limit=60, min_breaks=True, weights=None):
    """Phase 1: choose home/away patterns using only wishes of type A-C.
    Phase 2: fix those patterns and choose the matches with all wishes."""
    t0 = time.time()
    h_wishes = [w for w in data["wishes"] if w["type"] in H_ONLY_TYPES]
    m1 = build_model(data, wishes=h_wishes, weights=weights)
    r1 = solve(m1, time_limit, min_breaks)
    if r1["penalty"] is None:
        return None, {"status": "phase 1 failed: " + r1["status"]}
    fix = {(i, r): round(pyo.value(m1.h[i, r])) for i in data["teams"] for r in range(1, N_ROUNDS + 1)}
    m2 = build_model(data, weights=weights, fix_h=fix)
    r2 = solve(m2, time_limit, min_breaks=False)  # breaks are already fixed by the patterns
    r2["seconds"] = round(time.time() - t0, 1)
    return m2, r2


# --------------------------------------------------------------------------- report
def schedule_rows(m, data):
    rows = []
    for r in range(1, N_ROUNDS + 1):
        for (i, j) in m.PAIRS:
            if pyo.value(m.x[i, j, r]) > 0.5:
                rows.append({"round": r, "home": data["names"][i], "away": data["names"][j],
                             "top_match": int(i in data["top"] and j in data["top"])})
    return rows


def violated_wishes(m, data, weights=None):
    P = data["weights"] if weights is None else weights
    out = []
    for w, wish in enumerate(m._wishes):
        amount = round(pyo.value(m.v[w]))
        if amount > 0:
            out.append({**wish, "amount": amount, "penalty": amount * P[wish["level"]]})
    return out


def home_away_table(m, data):
    """One string per team, e.g. 'HAHAHHA...' (H = home)."""
    return {data["names"][i]: "".join("H" if pyo.value(m.h[i, r]) > 0.5 else "A"
                                      for r in range(1, N_ROUNDS + 1)) for i in data["teams"]}


def write_csv(path, rows, fields=None):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        Path(path).write_text("")
        return
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
