# Plain Vector vs Hybrid GraphRAG — Stratified Fresh Run

Questions: **5**; dataset SHA-256: `f16bcb883953d7a4e95820c9dc02848d73cae902fde01b7386eedbdc26aedb1d`

| ID | Tier | Vector fact | Hybrid fact | Fact Δ | Vector recall | Hybrid recall | Recall Δ | Vector ms | Hybrid ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `q_1hop_01` | 1-hop | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 5765.6 | 24755.7 |
| `q_2hop_01` | 2-hop | 0.500 | 0.000 | -0.500 | 0.000 | 0.500 | 0.500 | 1864.0 | 7459.7 |
| `q_3hop_01` | 3-hop | 0.667 | 0.667 | 0.000 | 0.000 | 0.500 | 0.500 | 3087.0 | 16177.9 |
| `q_agg_01` | aggregation | 0.000 | 0.000 | 0.000 | 0.500 | 0.000 | -0.500 | 2187.2 | 11258.9 |
| `q_oos_01` | out-of-scope | N/A | N/A | N/A | N/A | N/A | N/A | 2238.8 | 13073.2 |
