# Key findings (all numbers come from the scripts in this folder)

## 1. Recommended schedule (run_usecase.py)
- Optimal penalty **29**, **18 breaks** (the minimum possible; valid schedules range from 18 to 28).
- 4 of 60 wish constraints violated, all low priority (one level 3, two level 4, one level 5):
  - W09: Club Brugge home in round 2 (tie with Cercle; the shared stadium allows only one)
  - W12: Gent home in round 5 (the stadium is booked)
  - W14: FC Brussels home in round 6
  - W16: Standard home in round 10 (round 3 and round 10 can't both be home, because of the mirror)
- Ties: W09/W10 and W15/W16 cost the same, so the solver's choice between them is arbitrary. The committee decides those ties, not the model.

## 2. Value of optimization (baseline.py)
| Method | Penalty | Wishes violated |
|---|---|---|
| Manual: random placement of clubs in a valid template (average of 40,320) | ~54,500 | 15.1 |
| Careful manual: placement that respects stadium and police rules (average of 162) | 80 | 8.3 |
| Template model (best of all 40,320 placements) | 29 | 4 |
| Integrated model | 29 | 4 |

- Only 7.1% of placements respect the physical rules, and only 0.40% also respect the police rules. Finding a valid placement by hand is the hard part.
- Compared with careful manual work, optimization cuts the penalty by 64% and halves the number of violated wishes.
- Difference from the paper: there, the template model was much worse than the two-phase method. With 8 teams, the best template placement already reaches the optimum.

## 3. What drives the schedule (influence.py)
- **Scarce resource: home/away patterns.** Only 16 first-half patterns satisfy the hard rules, and the 8 clubs need 8 different ones. Club Brugge and Cercle get exactly opposite patterns, and so do Anderlecht and FC Brussels. The shared stadium and the Brussels police capacity are used in 14 of 14 rounds.
- **Binding wishes** (influence = how much the other wishes improve when this rule is dropped): W01 shared stadium (20), W10 Cercle round 2 (20), W02 Gent stadium booked (4), W15 Standard round 3 (4), W13 Anderlecht round 6 (1). All other rules cost nothing extra.
- **Price of granting a violated wish:** W14 FC Brussels +3, W09 and W16 +0 (a tie swaps which club loses), W12 Gent +14,996 (it would break a physical impossibility).
- **Hard rules:** the mirrored second half is the only hard rule with a cost. Dropping it lowers the penalty from 29 to 25 (Standard gets both festival weekends) and the breaks from 18 to 12. So the league's choice of a mirrored season costs 4 penalty points and 6 breaks. Relaxing "max two in a row" or "no break at start/end" gains nothing.
- Correction to an earlier explanation: FC Brussels' round-6 wish is not blocked by the police rule alone. Even without that rule, granting both Brussels clubs a home game in round 6 costs Genk its final home game. The real constraint is the pattern structure.

## 4. What-if analysis (whatif.py)
| Scenario | Penalty (base weights) | What it means |
|---|---|---|
| Base | 29 | |
| FC Brussels round 6 made hard | 32 | Granting it costs 3; Anderlecht and Standard pay |
| Both Bruges clubs home in round 2 | 30,009 | Physically impossible, twice (round 2 and its mirror, round 8) |
| All club wishes raised to level 2 | 32 | The losing club changes (Anderlecht instead of FC Brussels) |
| Broadcaster rule raised to level 1 | 29 | The TV rule costs nothing when solved jointly |
| All wishes weighted equally | 15,025 | The model sacrifices Gent's booked stadium: priority levels are essential |
| Allow 3 in a row / drop start-end break rule | 29 | These structural rules cost nothing here |

## 5. Comparison with the paper's two-phase method (two_phase_seeds.py, conflict_test.py)
- Use case: the two-phase method ends at 69 instead of 29 in **10 of 50 runs (20%)**. Phase 1 picks patterns blind to the broadcaster rule, and it has many equally good options. Without the broadcaster rule, it always reaches 29.
- Random wishes: the two-phase method is worse in only 4 of 25 instances. It is safe for scattered wishes and risky for season-wide match rules.

## 6. Why the paper used phases (scaling.py, 2 random instances per size)
| Teams | Binary variables | Integrated (s) | Two-phase (s) |
|---|---|---|---|
| 6–12 | 414–3,420 | ≤ 1.1 | ≤ 0.9 |
| 14 | 5,446 | 2.8 | 2.5 |
| 16 | 8,144 | 0.8 | 7.3 |
| 18 (real league) | 11,610 | **54** | **1.5** |

At the real size, the integrated model becomes much slower, even with a modern solver on simpler wishes than the real ones. That explains the paper's decomposition. With only 2 instances per size, treat this as an indication.

## Caveats to state on the poster
- When several schedules are equally good, the solver picks one arbitrarily, so small numbers (ties, the careful-manual average, the two-phase failure rate) can differ slightly between computers. The numbers here come from the run on Noa's Mac (Nov 12).
- All wishes are invented but realistic; the clubs are real (2006–07 Belgian First Division).
- Our two-phase method simplifies the paper's phase 1.
- Ties between equal-priority wishes are broken arbitrarily by the solver.
