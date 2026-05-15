# Table 4 — Test-set scaling by topology size

Per (topology size × agent). `s/m/l` are sized labs; `-` are P4/SDN labs (single size).

| Topology size | Agent | n | Overall | Final outcome | Mean input tokens | Mean time (s) |
|---|---|---:|---:|---:|---:|---:|
| s | ReAct (GPT-5) | 141 | 3.90 | 3.35 | **50,230** | 220.6 |
| s | CC-Baseline | 141 | 4.09 | 3.49 | 179,289 | 214.1 |
| s | SADE | 141 | **4.60** | **4.38** | 305,437 | **210.5** |
| m | ReAct (GPT-5) | 142 | 3.77 | 3.06 | **66,118** | 241.6 |
| m | CC-Baseline | 142 | 3.98 | 3.42 | 226,211 | **219.7** |
| m | SADE | 142 | **4.14** | **3.73** | 403,880 | 287.8 |
| l | ReAct (GPT-5) | 142 | 3.77 | 3.18 | **104,791** | 249.0 |
| l | CC-Baseline | 142 | 3.74 | 2.96 | 309,404 | **238.7** |
| l | SADE | 142 | **4.29** | **3.96** | 490,829 | 298.4 |
| - | ReAct (GPT-5) | 98 | 3.77 | 3.24 | **36,143** | 186.2 |
| - | CC-Baseline | 98 | 3.92 | 3.35 | 224,957 | **183.4** |
| - | SADE | 98 | **4.24** | **3.94** | 371,320 | 241.5 |