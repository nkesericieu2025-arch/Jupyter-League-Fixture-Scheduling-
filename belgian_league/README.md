# Belgian Soccer League – simplified scheduling model

8 teams, 14 rounds, mirrored double round-robin, solved with Pyomo + HiGHS.
Based on Goossens & Spieksma (2009), *Interfaces* 39(2).

## Setup
```bash
conda activate <your-env>
pip install pyomo highspy
```

## Files
| File | What it does |
|---|---|
| `data/teams.csv` | 8 clubs; `top = 1` marks the top teams used by wish type E |
| `data/priority_weights.csv` | Penalty per priority level (15000 / 500 / 20 / 4 / 1); change here for what-if analysis |
| `data/wishes_usecase.csv` | The designed use case: 21 wish rules (60 constraints once `round = all` is expanded) |
| `data/random/` | Random wish files written by the generator and the conflict test |
| `model.py` | Data loading, the MIP (constraints 5–13 of our formulation + type E), lexicographic break minimization, two-phase method, report helpers |
| `run_usecase.py` | Solves the use case with both methods and writes `results/` |
| `generate_random_wishes.py` | Writes one random wish file |
| `two_phase_seeds.py` | Re-runs the two-phase method with 50 solver seeds (phase 1 has many equally good patterns) |
| `baseline.py` | Manual baseline: places the clubs into a valid template in all 40,320 ways and compares with the optimum |
| `whatif.py` | What-if scenarios: hard wishes, changed priorities, relaxed rules |
| `influence.py` | Which wishes and hard rules drive the schedule, price of each violated wish, scarce resources (home/away patterns, shared stadium) |
| `scaling.py` | Solve times for 6-18 teams, integrated vs two-phase |
| `conflict_test.py` | Stress test: use case + n random wishes, many seeds, integrated vs two-phase |

## Run
```bash
python run_usecase.py
python baseline.py
python whatif.py
python two_phase_seeds.py
python influence.py
python scaling.py --sizes 6 8 10 12 14 16 18 --seeds 2 --time-limit 300
python generate_random_wishes.py --n 60 --seed 1 --conflict-share 0.4
python conflict_test.py --sizes 20 40 60 80 120 --seeds 5
python conflict_test.py --sizes 40 80 --seeds 10 --match-share 0.7 --out results/conflict_test_match70.csv
```

## Wish CSV format
`id, type, level, team_i, team_j, round, stakeholder, description[, conflict_group]`

`round` is a number from 1 to 14, or `all` (one constraint per round).

| Type | Meaning | Constraint |
|---|---|---|
| A | team i plays at home in round r | h[i,r] ≥ 1 − v |
| B | team i plays away in round r | h[i,r] ≤ v |
| C | teams i and j do not both host in round r | h[i,r] + h[j,r] ≤ 1 + v |
| D | teams i and j do not meet in round r | x[i,j,r] + x[j,i,r] ≤ v |
| E | at most one top-vs-top match in round r | Σ top matches in r ≤ 1 + v, v integer ≥ 0 |

To add a wish, add a row. No code changes are needed.

## Random wishes and conflict groups
`generate_random_wishes.py` mixes independent random wishes (levels 2–5, types A–E) with
deliberate conflict groups that cannot all be satisfied:

- **contradiction**: a club wants home in r, but the city says away in r
- **three_in_row**: home wanted in r, r+1, r+2, which breaks the two-in-a-row limit
- **mirror**: home wanted in r and r+7, but the second half flips home/away
- **neighbours**: two clubs want home in r, and the police say not both

`--conflict-share` sets roughly what fraction of the wishes belong to conflict groups.
`--match-share` sets the fraction of independent wishes of type D/E. These are the match-level wishes the two-phase method cannot see in phase 1.

Level 1 is not used for random wishes. It is reserved for real physical facts in the use case.

## Modelling notes
- **Lexicographic objective.** Stage 1 minimizes the penalty. Stage 2 fixes that penalty and minimizes breaks.
- **Two-phase method (simplified).** Phase 1 chooses home/away patterns using only wishes of types A–C. Phase 2 fixes those patterns and chooses the matches using all wishes. The paper's phase 1 is more elaborate.
- **Data.** All wish data are invented, realistic examples. The clubs are real, but their requests are not.
