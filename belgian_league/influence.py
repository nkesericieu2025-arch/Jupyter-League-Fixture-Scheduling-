"""
Which constraints drive the decision, and which resources are scarce? (brief, Section 6)

1. Influence of each wish rule: drop the rule, re-solve, and measure how much the OTHER
   wishes improve. A rule with influence > 0 is binding: it forces other wishes to be violated.
2. Price of each violated wish: force it to be satisfied and measure the extra penalty.
3. Influence of each hard (structural) rule: relax it and re-solve.
4. Scarce resources in the optimal schedule: home slots per round, the shared Bruges
   stadium, Brussels police capacity, top-match slots.

Output: results/influence_rules.csv, results/influence_hard_rules.csv, results/scarcity.csv
"""
from collections import Counter

import pyomo.environ as pyo

from model import load_data, build_model, solve, violated_wishes, write_csv, N_ROUNDS, HALF

TL = 120


def penalty_of(viol, rules=None):
    return sum(v["penalty"] for v in viol if rules is None or v["rule"] in rules)


def solve_case(data, wishes=None, hard_rules=(), hook=None):
    m = build_model(data, wishes=wishes)
    for w, wish in enumerate(m._wishes):
        if wish["rule"] in hard_rules:
            m.v[w].fix(0)
    if hook:
        hook(m)
    res = solve(m, TL, min_breaks=True)
    if res["penalty"] is None:
        return None, None, res
    return m, violated_wishes(m, data), res


def relax_mirror(m):
    m.mirror.deactivate()
    T = list(m.T)
    m.meet_once_2nd = pyo.Constraint([(i, j) for i in T for j in T if i < j], rule=lambda m, i, j:
        sum(m.x[i, j, r] + m.x[j, i, r] for r in range(HALF + 1, N_ROUNDS + 1)) == 1)
    m.swap_home = pyo.Constraint([(i, j) for i in T for j in T if i < j], rule=lambda m, i, j:
        sum(m.x[i, j, r] for r in m.R) == 1)  # each team hosts each opponent once


def allow_three(m):
    m.max_two_lo.deactivate()
    m.max_two_hi.deactivate()


def no_edge_breaks(m):
    m.no_start_break.deactivate()
    m.no_end_break.deactivate()


if __name__ == "__main__":
    data = load_data("data", ["wishes_usecase.csv"])
    m0, v0, r0 = solve_case(data)
    base = r0["penalty"]
    print(f"base penalty {base}, breaks {r0['breaks']}\n")

    # 1 + 2: wish rules
    rules = sorted({w["rule"] for w in data["wishes"]})
    desc = {w["rule"]: w["description"] for w in data["wishes"]}
    level = {w["rule"]: w["level"] for w in data["wishes"]}
    violated_rules = {v["rule"] for v in v0}
    rows = []
    for rule in rules:
        others_before = base - penalty_of(v0, {rule})
        _, v1, _ = solve_case(data, wishes=[w for w in data["wishes"] if w["rule"] != rule])
        influence = others_before - penalty_of(v1)
        price = ""
        if rule in violated_rules:
            _, v2, r2 = solve_case(data, hard_rules={rule})
            price = (r2["penalty"] - base) if v2 is not None else "infeasible"
        rows.append({"rule": rule, "level": level[rule], "violated_in_optimum": int(rule in violated_rules),
                     "influence_on_others": influence, "price_to_grant": price,
                     "description": desc[rule]})
    rows.sort(key=lambda r: -r["influence_on_others"])
    print(f"{'rule':<5}{'lvl':>4}{'violated':>9}{'influence':>10}{'price':>8}  description")
    for r in rows:
        print(f"{r['rule']:<5}{r['level']:>4}{r['violated_in_optimum']:>9}{r['influence_on_others']:>10}"
              f"{r['price_to_grant']!s:>8}  {r['description']}")
    write_csv("results/influence_rules.csv", rows)

    # 3: hard rules
    hard = []
    for name, hook in [("mirrored second half", relax_mirror), ("max two home/away in a row", allow_three),
                       ("no break at start/end", no_edge_breaks)]:
        _, v, r = solve_case(data, hook=hook)
        hard.append({"hard_rule_relaxed": name, "penalty": r["penalty"], "gain": base - r["penalty"],
                     "breaks": r["breaks"], "violated": " ".join(sorted(x["rule"] for x in v))})
    print(f"\n{'hard rule relaxed':<30}{'penalty':>8}{'gain':>6}{'breaks':>7}  violated")
    for h in hard:
        print(f"{h['hard_rule_relaxed']:<30}{h['penalty']:>8}{h['gain']:>6}{h['breaks']:>7}  {h['violated']}")
    write_csv("results/influence_hard_rules.csv", hard)

    # 4: scarcity in the optimal schedule
    H = {(i, r): round(pyo.value(m0.h[i, r])) for i in data["teams"] for r in range(1, N_ROUNDS + 1)}
    top = data["top"]
    scar = []
    for r in range(1, N_ROUNDS + 1):
        wants_home = sorted({w["i"] for w in data["wishes"] if w["type"] == "A" and w["r"] == r})
        top_games = sum(1 for (i, j) in m0.PAIRS if i in top and j in top and pyo.value(m0.x[i, j, r]) > 0.5)
        scar.append({"round": r, "home_slots": 4, "home_wishes": len(wants_home),
                     "home_wish_teams": " ".join(wants_home),
                     "bruges_stadium_used": H["CLU", r] + H["CER", r],
                     "brussels_home_matches": H["AND", r] + H["FCB", r], "top_matches": top_games})
    write_csv("results/scarcity.csv", scar)
    print(f"\n{'round':>5}{'home wishes':>12}{'Bruges stadium':>15}{'Brussels homes':>15}{'top matches':>12}")
    for s in scar:
        print(f"{s['round']:>5}{s['home_wishes']:>12}{s['bruges_stadium_used']:>15}"
              f"{s['brussels_home_matches']:>15}{s['top_matches']:>12}")
    used = Counter()
    for s in scar:
        used["bruges"] += s["bruges_stadium_used"]
        used["brussels"] += s["brussels_home_matches"]
        used["top"] += s["top_matches"]
    print(f"\nBruges stadium used in {used['bruges']}/14 rounds; Brussels police busy in "
          f"{used['brussels']}/14 rounds; top matches {used['top']} spread over 14 rounds (max 1 each)")
    # 5: the real scarce resource - valid home/away patterns
    import itertools
    valid = []
    for first in itertools.product([1, 0], repeat=HALF):
        full = list(first) + [1 - x for x in first]  # mirrored second half
        if full[0] == full[1] or full[-2] == full[-1]:
            continue  # break at start or end
        if any(full[r] == full[r + 1] == full[r + 2] for r in range(N_ROUNDS - 2)):
            continue  # three in a row
        valid.append("".join("H" if x else "A" for x in first))
    used_patterns = {data["names"][i]: "".join("H" if H[i, r] else "A" for r in range(1, HALF + 1))
                     for i in data["teams"]}
    print(f"\nOnly {len(valid)} first-half home/away patterns satisfy the hard rules; "
          f"the 8 clubs must use 8 different ones:")
    for team, p in used_patterns.items():
        print(f"  {team:<22} {p}")
    write_csv("results/valid_patterns.csv",
              [{"pattern": p, "used_by": ", ".join(t for t, q in used_patterns.items() if q == p)}
               for p in valid])
    print("Saved results/influence_rules.csv, influence_hard_rules.csv, scarcity.csv, valid_patterns.csv")
