
`before/notslow_a.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_startup_is_clean[ni]` | 14 | 0,13 | 0,24 | 0,24 |
| `test_startup_is_clean[al]` | 5 | 0,01 | 0,25 | 0,25 |
| `test_startup_is_clean[fe]` | 8 | 0,02 | 0,27 | 0,27 |
| `test_single_equilibrium[ni]` | 15 | 0,16 | 0,42 | 0,42 |
| `test_single_equilibrium[al]` | 17 | 0,63 | 1,05 | 1,14 |
| `test_single_equilibrium[fe]` | 16 | 0,34 | 1,39 | 1,43 |
| `test_temperature_scan[ni]` | 18 | 0,03 | 1,42 | 2,47 |
| `test_temperature_scan[al]` | 33 | 0,01 | 1,43 | 4,28 |
| `test_temperature_scan[fe]` | 38 | 0,01 | 1,44 | 4,12 |
| `test_concentration_scan[ni]` | 35 | 0,01 | 1,44 | 3,57 |
| `test_concentration_scan[al]` | 68 | 0,01 | 1,45 | 3,24 |
| `test_concentration_scan[fe]` | 38 | 0,00 | 1,45 | 3,23 |
| `test_energy_curve[ni]` | 12 | 0,02 | 1,47 | 2,66 |
| `test_energy_curve[al]` | 10 | 0,10 | 1,57 | 1,62 |
| `test_energy_curve[fe]` | 13 | 0,00 | 1,57 | 1,58 |
| `test_driving_force[ni]` | 13 | 0,08 | 1,65 | 1,66 |
| `test_driving_force[al]` | 16 | 0,07 | 1,72 | 1,80 |
| `test_driving_force[fe]` | 19 | -0,01 | 1,71 | 1,73 |
| `test_tzero_in_narrow_window[ni]` | 14 | 0,00 | 1,71 | 1,74 |
| `test_tzero_in_narrow_window[al]` | 10 | 0,01 | 1,73 | 1,74 |
| `test_tzero_in_narrow_window[fe]` | 59 | -0,01 | 1,72 | 1,73 |

`before/notslow_b.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_density_single[ni]` | 21 | 0,30 | 0,41 | 0,41 |
| `test_density_single[al]` | 34 | 0,64 | 1,05 | 1,14 |
| `test_density_single[fe]` | 40 | 0,37 | 1,42 | 1,46 |
| `test_density_estimated_warning_is_shown_to_user` | 60 | 0,72 | 2,14 | 2,56 |
| `test_density_temperature_scan[ni]` | 14 | -0,21 | 1,93 | 2,14 |
| `test_density_temperature_scan[al]` | 34 | 0,01 | 1,94 | 4,88 |
| `test_density_temperature_scan[fe]` | 32 | -0,17 | 1,77 | 4,61 |
| `test_elastic_vrh[ni]` | 17 | 0,02 | 1,78 | 1,79 |
| `test_elastic_vrh[al]` | 20 | 0,00 | 1,78 | 1,83 |
| `test_elastic_vrh[fe]` | 23 | 0,01 | 1,80 | 1,84 |
| `test_strengthening[ni]` | 8 | 0,00 | 1,80 | 1,80 |
| `test_strengthening[al]` | 6 | 0,00 | 1,80 | 1,80 |
| `test_strengthening[fe]` | 14 | 0,00 | 1,80 | 1,81 |
| `test_phase_map_needs_three_elements[ni]` | 13 | 0,00 | 1,80 | 1,81 |
| `test_phase_map_needs_three_elements[al]` | 6 | -0,00 | 1,80 | 1,80 |
| `test_phase_map_needs_three_elements[fe]` | 8 | 0,00 | 1,80 | 1,81 |
| `test_results_do_not_survive_a_database_change` | 22 | -0,00 | 1,80 | 1,81 |

`before/slow__test_solidification.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-ni]` | 32 | 0,35 | 0,46 | 0,47 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-al]` | 93 | 1,17 | 1,63 | 1,64 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-fe]` | 65 | 0,32 | 1,95 | 1,96 |
| `test_solidification[Только равновесное затвердевание-ni]` | 18 | -0,94 | 1,02 | 1,96 |
| `test_solidification[Только равновесное затвердевание-al]` | 95 | 0,69 | 1,71 | 1,72 |
| `test_solidification[Только равновесное затвердевание-fe]` | 59 | 0,25 | 1,96 | 1,97 |
| `test_solidification[Только Scheil–Gulliver-ni]` | 19 | -0,85 | 1,11 | 1,96 |
| `test_solidification[Только Scheil–Gulliver-al]` | 69 | 0,62 | 1,73 | 1,74 |
| `test_solidification[Только Scheil–Gulliver-fe]` | 62 | 0,25 | 1,97 | 1,99 |

`before/slow__test_binary_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_binary_diagram[ni]` | 28 | 0,31 | 0,41 | 0,44 |
| `test_binary_diagram[al]` | 64 | 0,86 | 1,27 | 1,29 |
| `test_binary_diagram[fe]` | 29 | 0,09 | 1,37 | 1,38 |

`before/slow__test_isopleth_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_isopleth_diagram[ni]` | 76 | 1,12 | 1,22 | 1,29 |
| `test_isopleth_diagram[al]` | 214 | 0,72 | 1,95 | 2,11 |
| `test_isopleth_diagram[fe]` | 73 | 0,10 | 2,04 | 2,09 |

`before/slow__test_ternary_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_ternary_diagram[ni]` | 52 | 0,68 | 0,78 | 0,79 |
| `test_ternary_diagram[al]` | 124 | 0,94 | 1,72 | 1,76 |
| `test_ternary_diagram[fe]` | 47 | 0,04 | 1,76 | 1,78 |

`before/slow__test_ternary_phase_map.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_ternary_phase_map[ni]` | 28 | 0,16 | 0,26 | 1,80 |
| `test_ternary_phase_map[al]` | 75 | 0,03 | 0,30 | 4,54 |
| `test_ternary_phase_map[fe]` | 50 | 0,02 | 0,31 | 4,52 |
