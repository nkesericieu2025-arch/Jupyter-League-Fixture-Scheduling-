"""Solve the designed use case (data/wishes_usecase.csv) with both methods and save results."""
import json
from collections import Counter

from model import (load_data, build_model, solve, solve_two_phase, schedule_rows,
                   violated_wishes, home_away_table, write_csv)

TIME_LIMIT = 120


def summarize(name, res, viol):
    print(f"\n=== {name} ===")
    print(f"status: {res['status']} | penalty: {res['penalty']} | breaks: {res['breaks']} "
          f"| time: {res['seconds']} s")
    by_level = Counter(v["level"] for v in viol)
    print("violated wishes by level:", dict(sorted(by_level.items())) or "none")
    for v in viol:
        amt = f" (x{v['amount']})" if v["amount"] > 1 else ""
        print(f"  {v['id']:<8} L{v['level']} {v['penalty']:>6}{amt}  {v['description']}")


if __name__ == "__main__":
    data = load_data("data", ["wishes_usecase.csv"])
    print(f"{len(data['teams'])} teams, {len(data['wishes'])} wish constraints "
          f"(from {len({w['rule'] for w in data['wishes']})} rules in the CSV)")

    m = build_model(data)
    res = solve(m, TIME_LIMIT)
    viol = violated_wishes(m, data)
    summarize("Integrated model", res, viol)
    print("\nHome/away patterns:")
    for team, pat in home_away_table(m, data).items():
        print(f"  {team:<22} {pat[:7]} | {pat[7:]}")

    m2, res2 = solve_two_phase(data, TIME_LIMIT)
    viol2 = violated_wishes(m2, data)
    summarize("Two-phase method", res2, viol2)

    fields = ["id", "rule", "type", "level", "i", "j", "r", "stakeholder", "amount", "penalty", "description"]
    write_csv("results/usecase_schedule.csv", schedule_rows(m, data))
    write_csv("results/usecase_violations_integrated.csv", viol, fields)
    write_csv("results/usecase_violations_two_phase.csv", viol2, fields)
    with open("results/usecase_summary.json", "w") as f:
        json.dump({"integrated": res, "two_phase": res2,
                   "patterns_integrated": home_away_table(m, data)}, f, indent=2)
    print("\nSaved results/ (schedule, violations, summary)")
