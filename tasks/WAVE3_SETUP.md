# Волна 3 — подготовка (один раз, до запуска 3F/3G/3H)
На Windows из C:\Users\gareg\Desktop\ThermoGar (main = после мержей волны 2):
```
git add tasks\WAVE3_SETUP.md tasks\WAVE3_COMMON.md tasks\WAVE3F_OPUS.md tasks\WAVE3G_OPUS.md tasks\WAVE3H_OPUS.md
git commit -m "Wave 3 task files"
git worktree remove ..\ThermoGar-w2a; git worktree remove ..\ThermoGar-w2b; git worktree prune
git branch -D wave2a-c15-app wave2b-fe-modules
git worktree add ..\ThermoGar-w3f -b wave3f-app-sections main
git worktree add ..\ThermoGar-w3g -b wave3g-kinetics main
git worktree add ..\ThermoGar-w3h -b wave3h-projects-docs main
git worktree list
```
