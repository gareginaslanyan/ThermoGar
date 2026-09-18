прогонов: 51
суммарное время: 6226 с = 1.73 ч
максимальный пик дерева: 4,86 ГиБ
красных файлов: 2 — test_parallel_integration.py, test_ui_g.py

| файл | режим | exit | итоговая строка pytest | итог | время, с | пик, ГиБ | мин. свободно, ГиБ |
|---|---|---:|---|---|---:|---:|---:|
| `test_backend_calculations.py` | -m "not slow" | 0 | `43 passed, 14 deselected, 4 warnings in 361.81s (0:06:01)` | зелёный | 365.2 | 1,73 | 7,04 |
| `test_database_repair.py` | -m "not slow" | 0 | `44 passed in 249.64s (0:04:09)` | зелёный | 252.8 | 2,89 | 6,14 |
| `test_density.py` | -m "not slow" | 0 | `66 passed in 182.61s (0:03:02)` | зелёный | 184.6 | 2,73 | 6,28 |
| `test_density_thermal_expansion.py` | -m "not slow" | 0 | `10 passed, 2 deselected in 0.58s` | зелёный | 2.0 | — | 9,03 |
| `test_dropped_phases_text.py` | -m "not slow" | 0 | `2 passed in 0.07s` | зелёный | 2.0 | — | 9,01 |
| `test_liquidus_bisection.py` | -m "not slow" | 5 | `2 deselected in 0.12s` | зелёный | 2.0 | — | 8,84 |
| `test_parallel_engine.py` | -m "not slow" | 0 | `15 passed in 62.42s (0:01:02)` | зелёный | 64.2 | 1,39 | 7,62 |
| `test_parallel_integration.py` | -m "not slow" | 2147483651 | `1 failed, 5 passed, 1 warning in 47.58s` | КРАСНЫЙ | 72.3 | 3,33 | 5,46 |
| `test_phase_presets.py` | -m "not slow" | 0 | `15 passed, 6 deselected in 46.23s` | зелёный | 48.2 | 1,52 | 5,84 |
| `test_phase_presets_control.py` | -m "not slow" | 5 | `1 deselected in 2.22s` | зелёный | 4.0 | 0,12 | 7,42 |
| `test_physical_overrides_toggle.py` | -m "not slow" | 0 | `11 passed in 187.88s (0:03:07)` | зелёный | 190.7 | 1,43 | 5,91 |
| `test_precipitation_bl35.py` | -m "not slow" | 0 | `11 passed, 1 warning in 36.33s` | зелёный | 38.2 | 0,37 | 7,65 |
| `test_precipitation_grid.py` | -m "not slow" | 0 | `32 passed, 13 warnings in 153.78s (0:02:33)` | зелёный | 156.6 | 0,84 | 7,34 |
| `test_ui_f.py` | -m "not slow" | 0 | `38 passed, 21 deselected in 624.15s (0:10:24)` | зелёный | 626.0 | 4,36 | 4,57 |
| `test_ui_g.py` | -m "not slow" | 1 | `8 failed, 21 passed, 3 deselected, 2 warnings in 170.13s (0:02:50)` | КРАСНЫЙ | 172.5 | 0,56 | 8,37 |
| `test_ui_h.py` | -m "not slow" | 0 | `24 passed, 2 deselected in 295.45s (0:04:55)` | зелёный | 296.9 | 0,54 | 8,23 |
| `test_wave15_z.py` | -m "not slow" | 0 | `15 passed, 2 warnings in 21.99s` | зелёный | 24.1 | 0,40 | 8,30 |
| `thermogar_active_state_io_test.py` | -m "not slow" | 0 | `5 passed, 2 warnings in 3.73s` | зелёный | 6.0 | 0,20 | 8,54 |
| `thermogar_converter_patch_test.py` | -m "not slow" | 5 | `no tests ran in 0.03s` | зелёный | 2.0 | — | 8,72 |
| `thermogar_db_cache_test.py` | -m "not slow" | 0 | `10 passed, 3 subtests passed in 0.30s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_diffusion_test.py` | -m "not slow" | 5 | `no tests ran in 0.57s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_fe_database_test.py` | -m "not slow" | 5 | `no tests ran in 1.92s` | зелёный | 4.0 | 0,15 | 8,56 |
| `thermogar_fe_internal_smoke_test.py` | -m "not slow" | 0 | `15 passed in 0.26s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_paths_test.py` | -m "not slow" | 0 | `6 passed in 0.16s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_physical_test.py` | -m "not slow" | 5 | `no tests ran in 0.02s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_precipitation_test.py` | -m "not slow" | 5 | `no tests ran in 0.03s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_properties_test.py` | -m "not slow" | 5 | `no tests ran in 0.10s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_restricted_fe_core_test.py` | -m "not slow" | 0 | `15 passed, 17 subtests passed in 2.77s` | зелёный | 4.0 | 0,14 | 8,57 |
| `thermogar_secure_io_test.py` | -m "not slow" | 0 | `19 passed in 0.49s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_self_test.py` | -m "not slow" | 5 | `no tests ran in 1.95s` | зелёный | 4.0 | 0,15 | 8,54 |
| `thermogar_state_migration_test.py` | -m "not slow" | 0 | `6 passed in 0.62s` | зелёный | 2.0 | — | 8,67 |
| `thermogar_verified_equilibrium_test.py` | -m "not slow" | 0 | `16 passed, 8 subtests passed in 1.07s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_verified_loaders_test.py` | -m "not slow" | 0 | `18 passed in 0.36s` | зелёный | 2.0 | — | 8,69 |
| `thermogar_verified_physical_test.py` | -m "not slow" | 0 | `24 passed in 1.01s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_verified_properties_test.py` | -m "not slow" | 0 | `39 passed, 5 subtests passed in 3.95s` | зелёный | 6.0 | 0,20 | 8,49 |
| `thermogar_verified_state_test.py` | -m "not slow" | 0 | `24 passed in 0.92s` | зелёный | 2.0 | — | 8,69 |
| `test_backend_calculations.py` | -m slow | 0 | `14 passed, 43 deselected, 2 warnings in 783.99s (0:13:03)` | зелёный | 786.4 | 1,77 | 7,15 |
| `test_density_thermal_expansion.py` | -m slow | 0 | `1 passed, 10 deselected, 1 xfailed in 36.75s` | зелёный | 38.1 | 1,35 | 7,54 |
| `test_liquidus_bisection.py` | -m slow | 0 | `2 passed in 262.42s (0:04:22)` | зелёный | 264.9 | 1,28 | 7,59 |
| `test_phase_presets.py` | -m slow | 0 | `6 passed, 15 deselected in 221.67s (0:03:41)` | зелёный | 224.7 | 1,70 | 7,12 |
| `test_phase_presets_control.py` | -m slow | 0 | `1 passed in 707.37s (0:11:47)` | зелёный | 710.2 | 3,03 | 5,87 |
| `test_ui_g.py` | -m slow | 1 | `2 failed, 1 passed, 29 deselected, 3 warnings in 176.91s (0:02:56)` | КРАСНЫЙ | 178.5 | 0,46 | 8,56 |
| `test_ui_h.py` | -m slow | 0 | `2 passed, 24 deselected in 47.80s` | зелёный | 50.1 | 1,44 | 7,58 |
| `test_ui_f.py` | -m slow | 0 | `21 passed, 38 deselected in 1156.50s (0:19:16)` | зелёный | 1159.5 | 4,86 | 4,40 |
| `thermogar_converter_patch_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 2.0 | — | 9,12 |
| `thermogar_diffusion_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 16.1 | 0,20 | 8,84 |
| `thermogar_fe_database_test.py` | сценарий | 0 | `Reports: D:\Pets\ThermoGar\results\validation\stage13_2` | зелёный | 176.5 | 2,68 | 6,37 |
| `thermogar_physical_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 2.1 | — | 9,09 |
| `thermogar_precipitation_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 24.1 | 0,27 | 8,73 |
| `thermogar_properties_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 4.0 | 0,17 | 8,85 |
| `thermogar_self_test.py` | сценарий | 0 | `==============================================================================` | зелёный | 34.1 | 0,90 | 8,06 |
