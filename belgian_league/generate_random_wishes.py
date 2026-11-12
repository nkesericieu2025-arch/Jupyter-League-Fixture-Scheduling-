"""
Generate a reproducible set of random wishes, part of them in deliberate conflict groups.

Conflict generators (rows of one group share the same conflict_group id):
  contradiction - a club asks for home in round r, another stakeholder asks for away in round r
  three_in_row  - a club asks for home in r, r+1 and r+2 (impossible: max two in a row)
  mirror        - a club asks for home in r and r+7 (impossible: the second half flips home/away)
  neighbours    - two clubs ask for home in round r, police ask that they don't both host

Usage:
  python generate_random_wishes.py --n 60 --seed 1 --conflict-share 0.4
  -> data/random/wishes_n60_seed1.csv
"""
import argparse
import csv
import random
from pathlib import Path

N_ROUNDS, HALF = 14, 7
FIELDS = ["id", "type", "level", "team_i", "team_j", "round", "stakeholder", "description", "conflict_group"]
# Level 1 is kept for real physical facts in the use case, so random wishes use levels 2-5.
LEVEL_MIX = {2: 0.10, 3: 0.25, 4: 0.30, 5: 0.35}
TYPE_MIX = {"A": 0.35, "B": 0.25, "C": 0.15, "D": 0.15, "E": 0.10}


def _pick(rng, mix):
    return rng.choices(list(mix), weights=list(mix.values()))[0]


def _row(n, k, lvl, i, j, r, who, text, group=""):
    return {"id": f"R{n:03d}", "type": k, "level": lvl, "team_i": i or "", "team_j": j or "",
            "round": r, "stakeholder": who, "description": text, "conflict_group": group}


def independent_wish(rng, teams, n):
    k, lvl, r = _pick(rng, TYPE_MIX), _pick(rng, LEVEL_MIX), rng.randint(1, N_ROUNDS)
    i, j = rng.sample(teams, 2)
    text = {
        "A": f"{i} wants to play at home in round {r}",
        "B": f"{i} wants to play away in round {r}",
        "C": f"{i} and {j} should not both host in round {r}",
        "D": f"{i} and {j} should not meet in round {r}",
        "E": f"at most one top match in round {r}",
    }[k]
    who = {"A": "Club", "B": "Club", "C": "Police", "D": "Police", "E": "Broadcaster"}[k]
    if k in "AB":
        j = None
    if k == "E":
        i = j = None
    return [_row(n, k, lvl, i, j, r, who, text)]


def conflict_group(rng, teams, n, g):
    kind = rng.choice(["contradiction", "three_in_row", "mirror", "neighbours"])
    gid = f"G{g:02d}-{kind}"
    i, j = rng.sample(teams, 2)
    rows = []
    if kind == "contradiction":
        r = rng.randint(1, N_ROUNDS)
        rows.append(_row(n, "A", _pick(rng, LEVEL_MIX), i, None, r, "Club", f"{i} wants home in round {r}", gid))
        rows.append(_row(n + 1, "B", _pick(rng, LEVEL_MIX), i, None, r, "Local government",
                         f"{i} cannot host in round {r} (city event)", gid))
    elif kind == "three_in_row":
        r = rng.randint(1, N_ROUNDS - 2)
        for k in range(3):
            rows.append(_row(n + k, "A", _pick(rng, LEVEL_MIX), i, None, r + k, "Club",
                             f"{i} wants home in round {r + k}", gid))
    elif kind == "mirror":
        r = rng.randint(1, HALF)
        for rr in (r, r + HALF):
            rows.append(_row(n + len(rows), "A", _pick(rng, LEVEL_MIX), i, None, rr, "Club",
                             f"{i} wants home in round {rr}", gid))
    else:  # neighbours
        r = rng.randint(1, N_ROUNDS)
        rows.append(_row(n, "A", _pick(rng, LEVEL_MIX), i, None, r, "Club", f"{i} wants home in round {r}", gid))
        rows.append(_row(n + 1, "A", _pick(rng, LEVEL_MIX), j, None, r, "Club", f"{j} wants home in round {r}", gid))
        rows.append(_row(n + 2, "C", _pick(rng, LEVEL_MIX), i, j, r, "Police",
                         f"{i} and {j} should not both host in round {r}", gid))
    return rows


def set_match_share(share):
    """Share of independent wishes that are match-level (types D and E), which the
    two-phase method cannot see in phase 1. Default mix gives 0.25."""
    global TYPE_MIX
    ab_c = {"A": 0.35, "B": 0.25, "C": 0.15}
    s = sum(ab_c.values())
    TYPE_MIX = {k: v / s * (1 - share) for k, v in ab_c.items()}
    TYPE_MIX.update({"D": share * 0.6, "E": share * 0.4})


def generate(teams, n, seed, conflict_share=0.4, match_share=None):
    """Return about n wish rows; roughly conflict_share of them belong to conflict groups."""
    if match_share is not None:
        set_match_share(match_share)
    rng = random.Random(seed)
    rows, g = [], 1
    while len(rows) < n:
        if rng.random() < conflict_share:
            new = conflict_group(rng, teams, len(rows) + 1, g)
            g += 1
        else:
            new = independent_wish(rng, teams, len(rows) + 1)
        rows += new
    return rows[:n]


def read_teams(data_dir="data"):
    with open(Path(data_dir) / "teams.csv", newline="", encoding="utf-8") as f:
        return [t["code"] for t in csv.DictReader(f)]


def save(rows, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="number of random wishes")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--conflict-share", type=float, default=0.4)
    ap.add_argument("--match-share", type=float, default=None,
                    help="share of independent wishes of type D/E (default 0.25)")
    a = ap.parse_args()
    rows = generate(read_teams(), a.n, a.seed, a.conflict_share, a.match_share)
    out = f"data/random/wishes_n{a.n}_seed{a.seed}.csv"
    save(rows, out)
    groups = len({r["conflict_group"] for r in rows if r["conflict_group"]})
    print(f"wrote {len(rows)} wishes ({groups} conflict groups) to {out}")
