"""
Scaling test: how hard does the integrated model get as the league grows?
Explains why the paper (18 teams) split the problem into phases.

For each league size n we build a synthetic instance with the same structure as the use case:
a shared stadium (teams 1-2), a police pair (teams 3-4), the broadcaster rule, and about
5 random club/police wishes per team. Each instance is solved with a time limit.

Usage: python scaling.py --sizes 6 8 10 12 --seeds 3 --time-limit 120
Output: results/scaling.csv
"""
import argparse
import random
import statistics as st
import time

import pyomo.environ as pyo

from model import build_model, solve_two_phase, write_csv

WEIGHTS = {1: 15000, 2: 500, 3: 20, 4: 4, 5: 1}


def instance(n, seed):
    rng = random.Random(seed)
    teams = [f"T{k:02d}" for k in range(1, n + 1)]
    nr = 2 * (n - 1)
    wishes = []

    def add(rule, k, lvl, i, j, r):
        wishes.append({"id": f"{rule}-r{r}", "rule": rule, "type": k, "level": lvl, "i": i, "j": j,
                       "r": r, "stakeholder": "", "description": "", "group": ""})
    for r in range(1, nr + 1):
        add("stadium", "C", 1, teams[0], teams[1], r)
        add("police", "C", 2, teams[2], teams[3], r)
        add("tv", "E", 3, None, None, r)
    for k in range(5 * n):
        typ = rng.choice("AABBCD")
        i, j = rng.sample(teams, 2)
        add(f"R{k}", typ, rng.choice([2, 3, 4, 4, 5, 5]), i, j if typ in "CD" else None,
            rng.randint(1, nr))
    return {"teams": teams, "names": {t: t for t in teams}, "top": teams[:4],
            "weights": WEIGHTS, "wishes": wishes}


def solve_timed(m, tl):
    solver = pyo.SolverFactory("appsi_highs")
    solver.config.time_limit = tl
    t0 = time.time()
    res = solver.solve(m, load_solutions=False)
    secs = time.time() - t0
    status = str(res.solver.termination_condition)
    try:
        m.solutions.load_from(res)
        obj = round(pyo.value(m.penalty))
    except Exception:
        obj = None
    lb = res.problem.lower_bound
    gap = None if obj in (None, 0) or lb is None else max(0.0, (obj - lb) / obj)
    return status, obj, gap, round(secs, 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[6, 8, 10, 12])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--time-limit", type=float, default=120)
    a = ap.parse_args()
    rows = []
    for n in a.sizes:
        for seed in range(1, a.seeds + 1):
            data = instance(n, seed)
            m = build_model(data)
            status, obj, gap, secs = solve_timed(m, a.time_limit)
            t0 = time.time()
            _, r2 = solve_two_phase(data, a.time_limit, min_breaks=False)
            row = {"teams": n, "rounds": 2 * (n - 1), "seed": seed, "binary_vars": len(m.x) + len(m.h) + len(m.b),
                   "wish_constraints": len(data["wishes"]), "integrated_status": status,
                   "integrated_penalty": obj, "integrated_gap": None if gap is None else round(gap, 3),
                   "integrated_seconds": secs, "two_phase_penalty": r2.get("penalty"),
                   "two_phase_seconds": round(time.time() - t0, 1)}
            rows.append(row)
            print(f"n={n:<3} seed={seed} vars={row['binary_vars']:<6} integrated: {status:<13} "
                  f"pen={obj} gap={row['integrated_gap']} {secs}s | two-phase pen={row['two_phase_penalty']} "
                  f"{row['two_phase_seconds']}s", flush=True)
    write_csv("results/scaling.csv", rows)
    print(f"\n{'teams':>5}{'vars':>8}{'integrated s':>14}{'solved to opt':>15}{'two-phase s':>13}")
    for n in a.sizes:
        rs = [r for r in rows if r["teams"] == n]
        opt = sum(r["integrated_status"] == "optimal" for r in rs)
        print(f"{n:>5}{rs[0]['binary_vars']:>8}{st.mean(r['integrated_seconds'] for r in rs):>14.1f}"
              f"{opt:>11}/{len(rs):<3}{st.mean(r['two_phase_seconds'] for r in rs):>13.1f}")
    print("Saved results/scaling.csv")
