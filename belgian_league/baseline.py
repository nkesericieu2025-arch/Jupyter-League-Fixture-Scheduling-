"""
Baseline schedules, to measure the value of optimization (like Table 3 in the paper).

1. Build one valid template: a schedule for 8 anonymous slots (1..8) that satisfies all hard
   rules with the minimum number of breaks (solved with the model, no wishes).
2. "Manual" baseline: a committee places the 8 clubs into the template slots without
   optimization. We evaluate ALL 8! = 40,320 placements and report the average and spread.
3. "Template model": the best of the 40,320 placements (the paper's first approach).
4. Integrated model: the full optimization (model.py).

Output: results/baseline_summary.csv, results/baseline_all_placements.csv
"""
import itertools
import statistics as st
from collections import Counter

import pyomo.environ as pyo

from model import load_data, build_model, solve, violated_wishes, N_ROUNDS, write_csv

SLOTS = [f"S{k}" for k in range(1, 9)]


def make_template(data):
    """A valid schedule for anonymous slots: hard rules only, minimum breaks."""
    anon = {**data, "teams": SLOTS, "names": {s: s for s in SLOTS}, "top": [], "wishes": []}
    m = build_model(anon)
    solve(m, 120, min_breaks=True)
    matches = [(i, j, r) for (i, j) in m.PAIRS for r in range(1, N_ROUNDS + 1)
               if pyo.value(m.x[i, j, r]) > 0.5]
    breaks = round(pyo.value(m.breaks))
    return matches, breaks


def evaluate(matches, data):
    """Penalty of a fixed schedule, using exactly the same wish rules as the model."""
    home = {(i, r): 0 for i in data["teams"] for r in range(1, N_ROUNDS + 1)}
    meets = set()
    top_games = Counter()
    top = set(data["top"])
    for i, j, r in matches:
        home[i, r] = 1
        meets.add((frozenset((i, j)), r))
        if i in top and j in top:
            top_games[r] += 1
    P = data["weights"]
    total, violated = 0, []
    for w in data["wishes"]:
        k, i, j, r = w["type"], w["i"], w["j"], w["r"]
        amount = {
            "A": 1 - home.get((i, r), 0),
            "B": home.get((i, r), 0),
            "C": max(0, home.get((i, r), 0) + home.get((j, r), 0) - 1),
            "D": 1 if (frozenset((i, j)), r) in meets else 0,
            "E": max(0, top_games[r] - 1),
        }[k]
        if amount:
            total += amount * P[w["level"]]
            violated.append(w)
    return total, violated


if __name__ == "__main__":
    data = load_data("data", ["wishes_usecase.csv"])
    template, t_breaks = make_template(data)
    print(f"template: {len(template)} matches, {t_breaks} breaks")

    placements = []
    for perm in itertools.permutations(data["teams"]):
        slot_to_team = dict(zip(SLOTS, perm))
        sched = [(slot_to_team[i], slot_to_team[j], r) for i, j, r in template]
        pen, viol = evaluate(sched, data)
        lv = Counter(w["level"] for w in viol)
        placements.append({"placement": " ".join(perm), "penalty": round(pen), "violated": len(viol),
                           **{f"violated_L{k}": lv.get(k, 0) for k in range(1, 6)}})
    pens = [p["penalty"] for p in placements]
    best = min(placements, key=lambda p: p["penalty"])
    ok_L1 = sum(p["violated_L1"] == 0 for p in placements)
    # A committee that checks the stadium and police rules by hand, but optimizes nothing else
    careful = [p for p in placements if p["violated_L1"] == 0 and p["violated_L2"] == 0]

    m = build_model(data)
    integ = solve(m, 120, min_breaks=True)
    iv = Counter(w["level"] for w in violated_wishes(m, data))

    summary = [
        {"method": "Manual (average random placement)", "penalty": round(st.mean(pens)),
         "violated": round(st.mean(p["violated"] for p in placements), 1),
         "violated_L1": round(st.mean(p["violated_L1"] for p in placements), 1),
         "violated_L2": round(st.mean(p["violated_L2"] for p in placements), 1), "breaks": t_breaks},
        {"method": f"Careful manual (avg of {len(careful)} placements with no L1/L2 violation)",
         "penalty": round(st.mean(p["penalty"] for p in careful)),
         "violated": round(st.mean(p["violated"] for p in careful), 1),
         "violated_L1": 0, "violated_L2": 0, "breaks": t_breaks},
        {"method": "Template model (best of 40,320 placements)", "penalty": best["penalty"],
         "violated": best["violated"], "violated_L1": best["violated_L1"],
         "violated_L2": best["violated_L2"], "breaks": t_breaks},
        {"method": "Integrated model (optimal)", "penalty": integ["penalty"], "violated": sum(iv.values()),
         "violated_L1": iv.get(1, 0), "violated_L2": iv.get(2, 0), "breaks": integ["breaks"]},
    ]
    print(f"\n{"method":<60}{'penalty':>9}{'violated':>10}{'L1':>6}{'L2':>6}{'breaks':>8}")
    for s in summary:
        print(f"{s["method"]:<60}{s['penalty']:>9}{s['violated']!s:>10}{s['violated_L1']!s:>6}"
              f"{s['violated_L2']!s:>6}{s['breaks']!s:>8}")
    print(f"\nplacements with no level-1 violation: {ok_L1} of {len(placements)} "
          f"({100 * ok_L1 / len(placements):.1f}%)")
    print(f"worst placement penalty: {max(pens)}")
    write_csv("results/baseline_summary.csv", summary)
    write_csv("results/baseline_all_placements.csv", placements)
    print("Saved results/baseline_summary.csv and results/baseline_all_placements.csv")
