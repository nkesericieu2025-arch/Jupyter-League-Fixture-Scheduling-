"""
What-if analysis: change one thing, re-solve, compare with the base case.

Scenarios
  base              the use case as it is
  hard_W14          make FC Brussels' round-6 home wish a hard rule (price of a wish)
  hard_W09_W10      both Bruges clubs get their round-2 home game (impossible: shared stadium)
  clubs_level2      every club wish moves to level 2 (clubs gain power on the committee)
  tv_level1         the broadcaster rule W07 becomes level 1
  equal_weights     every wish weighs 1 (no priorities: just count violated wishes)
  allow_three       allow three consecutive home or away games
  no_break_rule     drop the 'no break at start/end of season' rule

Every scenario is also scored with the BASE weights, so penalties are comparable.
Output: results/whatif_summary.csv
"""
import copy
from collections import Counter

import pyomo.environ as pyo

from model import load_data, build_model, solve, violated_wishes, write_csv


def scenario(name, data):
    """Return (data, weights, model_hook) for a scenario."""
    d = copy.deepcopy(data)
    weights = dict(d["weights"])
    hard, hook = [], None
    if name == "hard_W14":
        hard = ["W14"]
    elif name == "hard_W09_W10":
        hard = ["W09", "W10"]
    elif name == "clubs_level2":
        for w in d["wishes"]:
            if w["stakeholder"] == "Club":
                w["level"] = 2
    elif name == "tv_level1":
        for w in d["wishes"]:
            if w["rule"] == "W07":
                w["level"] = 1
    elif name == "equal_weights":
        weights = {k: 1 for k in weights}
    elif name == "allow_three":
        def hook(m):
            m.max_two_lo.deactivate()
            m.max_two_hi.deactivate()
            # still forbid four in a row
            m.max_three = pyo.ConstraintList()
            for i in m.T:
                for r in range(1, 12):
                    s = sum(m.h[i, r + k] for k in range(4))
                    m.max_three.add(s >= 1)
                    m.max_three.add(s <= 3)
    elif name == "no_break_rule":
        def hook(m):
            m.no_start_break.deactivate()
            m.no_end_break.deactivate()
    return d, weights, hard, hook


def run(name, base_data, time_limit=120):
    d, weights, hard, hook = scenario(name, base_data)
    m = build_model(d, weights=weights)
    for w, wish in enumerate(m._wishes):
        if wish["rule"] in hard:
            m.v[w].fix(0)
    if hook:
        hook(m)
    res = solve(m, time_limit, min_breaks=True)
    if res["penalty"] is None:
        return {"scenario": name, "status": res["status"]}, []
    viol = violated_wishes(m, d, weights)
    base_w = base_data["weights"]
    level_of = {w["id"]: w["level"] for w in base_data["wishes"]}
    pen_base = sum(v["amount"] * base_w[level_of[v["id"]]] for v in viol)
    lv = Counter(level_of[v["id"]] for v in viol)
    return {
        "scenario": name, "status": res["status"],
        "penalty_scenario_weights": res["penalty"], "penalty_base_weights": round(pen_base),
        "violated": len(viol), **{f"L{k}": lv.get(k, 0) for k in range(1, 6)},
        "breaks": res["breaks"],
        "violated_wishes": " ".join(sorted({v["id"] if v["type"] != "E" else v["id"] for v in viol})),
    }, viol


if __name__ == "__main__":
    data = load_data("data", ["wishes_usecase.csv"])
    names = ["base", "hard_W14", "hard_W09_W10", "clubs_level2", "tv_level1",
             "equal_weights", "allow_three", "no_break_rule"]
    rows = []
    for n in names:
        row, _ = run(n, data)
        rows.append(row)
    print(f"{'scenario':<15}{'penalty*':>9}{'viol.':>6}{'L1':>4}{'L2':>4}{'L3':>4}{'L4':>4}{'L5':>4}"
          f"{'breaks':>7}  violated wishes")
    for r in rows:
        if "violated" not in r:
            print(f"{r['scenario']:<15} {r['status']}")
            continue
        print(f"{r['scenario']:<15}{r['penalty_base_weights']:>9}{r['violated']:>6}"
              + "".join(f"{r[f'L{k}']:>4}" for k in range(1, 6))
              + f"{r['breaks']:>7}  {r['violated_wishes']}")
    print("* penalty measured with the base weights, so all rows are comparable")
    write_csv("results/whatif_summary.csv", rows)
    print("Saved results/whatif_summary.csv")
