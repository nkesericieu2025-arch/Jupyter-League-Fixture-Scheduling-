"""
Stress test: use-case wishes + n random wishes, for several sizes and seeds.
Compares the integrated model with the two-phase method and records which wishes are violated.

Usage:
  python conflict_test.py                          # default sweep
  python conflict_test.py --sizes 20 60 --seeds 3 --conflict-share 0.6
  python conflict_test.py --no-base                # random wishes only
Output: results/conflict_test.csv (one row per instance) and a summary printed per size.
"""
import argparse
import statistics as st
from collections import Counter

from generate_random_wishes import generate, read_teams, save
from model import load_data, build_model, solve, solve_two_phase, violated_wishes, write_csv

ap = argparse.ArgumentParser()
ap.add_argument("--sizes", type=int, nargs="+", default=[20, 40, 60, 80, 120])
ap.add_argument("--seeds", type=int, default=5)
ap.add_argument("--conflict-share", type=float, default=0.4)
ap.add_argument("--match-share", type=float, default=None,
                help="share of independent random wishes of type D/E (default 0.25)")
ap.add_argument("--out", default="results/conflict_test.csv")
ap.add_argument("--time-limit", type=float, default=60)
ap.add_argument("--no-base", action="store_true", help="do not include the use-case wishes")
a = ap.parse_args()

teams = read_teams()
base = [] if a.no_base else ["wishes_usecase.csv"]
records = []
for n in a.sizes:
    for seed in range(1, a.seeds + 1):
        rows = generate(teams, n, seed, a.conflict_share, a.match_share)
        tag = "" if a.match_share is None else f"_match{round(a.match_share * 100)}"
        save(rows, f"data/random/wishes_n{n}_seed{seed}{tag}.csv")
        data = load_data("data", base, extra_rows=rows)

        m = build_model(data)
        res = solve(m, a.time_limit, min_breaks=False)
        viol = violated_wishes(m, data)
        _, res2 = solve_two_phase(data, a.time_limit, min_breaks=False)

        lv = Counter(v["level"] for v in viol)
        rec = {
            "n_random": n, "seed": seed, "wish_constraints": len(data["wishes"]),
            "conflict_groups": len({r["conflict_group"] for r in rows if r["conflict_group"]}),
            "integrated_penalty": res["penalty"], "two_phase_penalty": res2.get("penalty"),
            "violated_total": len(viol),
            "violated_in_conflict_groups": sum(1 for v in viol if v["group"]),
            **{f"violated_L{k}": lv.get(k, 0) for k in range(1, 6)},
            "integrated_status": res["status"], "two_phase_status": res2.get("status"),
            "integrated_seconds": res["seconds"], "two_phase_seconds": res2.get("seconds"),
        }
        records.append(rec)
        print(f"n={n:<4} seed={seed}  integrated={rec['integrated_penalty']:<6} "
              f"two-phase={rec['two_phase_penalty']:<6} violated={rec['violated_total']:<3} "
              f"({res['seconds']} s / {res2.get('seconds')} s)")

write_csv(a.out, records)

print("\nSummary per size (means over seeds)")
print(f"{'n':>4} {'integrated':>11} {'two-phase':>10} {'2P worse':>9} {'violated':>9} {'in groups':>10}")
for n in a.sizes:
    rs = [r for r in records if r["n_random"] == n and r["two_phase_penalty"] is not None]
    if not rs:
        continue
    worse = sum(r["two_phase_penalty"] > r["integrated_penalty"] for r in rs)
    print(f"{n:>4} {st.mean(r['integrated_penalty'] for r in rs):>11.1f} "
          f"{st.mean(r['two_phase_penalty'] for r in rs):>10.1f} {worse:>5}/{len(rs):<3} "
          f"{st.mean(r['violated_total'] for r in rs):>9.1f} "
          f"{st.mean(r['violated_in_conflict_groups'] for r in rs):>10.1f}")
print(f"\nSaved {a.out}")
