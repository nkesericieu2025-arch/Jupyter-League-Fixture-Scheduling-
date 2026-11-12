"""Phase 1 usually has many equally good home/away patterns. Re-run the two-phase method
with different solver seeds to see how much its result depends on that choice."""
import argparse
from collections import Counter
from model import load_data, build_model, solve, solve_two_phase, write_csv

ap = argparse.ArgumentParser()
ap.add_argument("--runs", type=int, default=50)
ap.add_argument("--wishes", default="wishes_usecase.csv")
a = ap.parse_args()
data = load_data("data", [a.wishes])
best = solve(build_model(data), 60, min_breaks=False)["penalty"]
rows = []
for s in range(1, a.runs + 1):
    _, r = solve_two_phase(data, 60, min_breaks=True, seed=s)
    rows.append({"seed": s, "two_phase_penalty": r["penalty"], "integrated_penalty": best})
    print(f"seed {s:>2}: two-phase {r['penalty']}  (integrated optimum {best})")
c = Counter(r["two_phase_penalty"] for r in rows)
print("\ndistribution of two-phase penalties:", dict(sorted(c.items())))
print(f"two-phase worse than integrated in {sum(r['two_phase_penalty'] > best for r in rows)}/{len(rows)} runs")
write_csv("results/two_phase_seeds.csv", rows)
