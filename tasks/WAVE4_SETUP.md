# Волна 4 (финал) — подготовка
```
cd C:\Users\gareg\Desktop\ThermoGar
git add tasks\WAVE4_SETUP.md tasks\WAVE4A_OPUS.md tasks\WAVE4B_OPUS.md
git commit -m "Wave 4 task files"
git worktree remove ..\ThermoGar-w3f; git worktree remove ..\ThermoGar-w3g; git worktree remove ..\ThermoGar-w3h; git worktree prune
git branch -D wave3f-app-sections wave3g-kinetics wave3h-projects-docs
git worktree add ..\ThermoGar-w4a -b wave4a-release main
git worktree add ..\ThermoGar-w4b -b wave4b-regression main
git worktree list
```
4A — релизная сборка и установка (нужен Gar для UAC-кликов); 4B — полный регресс, может идти параллельно.
