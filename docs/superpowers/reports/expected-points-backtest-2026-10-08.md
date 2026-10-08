# Expected points backtest (2026-10-08)

Model version: `hgb-poisson-2026-10`. Walk-forward: each gameweek predicted by a model trained only on earlier gameweeks, compared with the official number from the snapshot just before it.

- Gameweeks: 38, player-gameweeks: 28855
- Average error, ours: 0.953
- Average error, official: 1.083
- Captain (most-selected squad each week): ours better 19, official better 8, same 11
- Passes: yes

| Position | Ours | Official | Players |
|---|---|---|---|
| Goalkeepers | 0.605 | 0.755 | 3305 |
| Defenders | 1.101 | 1.255 | 9440 |
| Midfielders | 0.901 | 1.027 | 12891 |
| Forwards | 1.081 | 1.136 | 3219 |
