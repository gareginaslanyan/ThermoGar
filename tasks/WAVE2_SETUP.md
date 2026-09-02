# Волна 2 — подготовка (выполнить ОДИН раз, до запуска 2A/2B)
На Windows, из C:\Users\gareg\Desktop\ThermoGar, ветка main актуальна (волна 1 смержена).
Убрать старые worktree волны 1, если ещё не убраны, и создать новые:
```
git worktree remove ..\ThermoGar-w1a; git worktree remove ..\ThermoGar-w1b; git worktree remove ..\ThermoGar-w1c
git worktree prune
git branch -D wave1a-unfreeze wave1b-installer wave1c-backend-tests
git worktree add ..\ThermoGar-w2a -b wave2a-c15-app main
git worktree add ..\ThermoGar-w2b -b wave2b-fe-modules main
git worktree list
```
2A работает в ThermoGar-w2a, 2B — в ThermoGar-w2b. Python и базы — по абсолютным путям из основного репо
(C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe). _archive_codex не трогать и не добавлять в git.
Мержи в main делает мастер проекта отдельно, НЕ исполнители.
