# 0.3.1 — волна 5: подготовка (утро, один раз, из C:\Users\gareg\Desktop\ThermoGar)

```
$env:GIT_OPTIONAL_LOCKS='0'
# хвосты после релиза
Add-Content .gitignore "results/validation/"
git add .gitignore tasks\WAVE4A_OPUS.md docs\FEATURES.md tasks\WAVE5_SETUP.md tasks\WAVE5_COMMON.md tasks\WAVE5A_OPUS.md tasks\WAVE5B_OPUS.md tasks\WAVE5C_OPUS.md
git commit -m "Housekeeping after 0.3.0; FEATURES.md; wave 5 task files"
git worktree remove --force ..\ThermoGar-w1a; git worktree remove --force ..\ThermoGar-w3f; git worktree remove --force ..\ThermoGar-w3g; git worktree prune
git branch -D wave1a-unfreeze wave3f-app-sections wave3g-kinetics 2>$null
# GitHub (после создания пустого приватного репо ThermoGar в браузере)
git remote add origin https://github.com/<логин>/ThermoGar.git
git push -u origin main --tags
# worktree волны 5
git worktree add ..\ThermoGar-w5a -b wave5a-phase-presets main
git worktree add ..\ThermoGar-w5b -b wave5b-parallel-engine main
git worktree add ..\ThermoGar-w5c -b wave5c-backlog main
git worktree list
```
Порядок мержа после приёмки: 5C → 5A → 5B(модуль) → волна 6 (интеграция параллели в приложение, регресс, сборка 0.3.1).
