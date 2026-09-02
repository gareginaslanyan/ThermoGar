# Восстановление: три исполнителя в одном рабочем дереве (2026-09-02)

## Что случилось
Ветки `wave1a/1b/1c` созданы в одной папке `C:\Users\gareg\Desktop\ThermoGar`. Исполнители переключали
ветки друг у друга: сейчас checkout = `wave1c-backend-tests`, в индексе — staged-переносы 1B (packaging → _archive_codex),
у 1A закоммичен только шаг 1. Дальше так работать нельзя. Решение — `git worktree`: каждому исполнителю своя папка.

## Шаги (выполнить ОДНИМ исполнителем, остальные остановлены)
Все команды из `C:\Users\gareg\Desktop\ThermoGar`.

1. Убедиться, что ни один другой Opus/python/streamlit не работает в папке. Удалить `.git\index.lock`, если есть.
2. Сохранить работу 1B (staged-переносы в индексе принадлежат ветке 1B):
   ```
   git checkout wave1b-installer          # тот же коммит, индекс/дерево сохраняются
   git add -A packaging _archive_codex/packaging
   git commit -m "Wave 1B WIP: codex packaging scripts moved to _archive_codex"
   ```
   Если `checkout` отказывается — `git stash`, `git checkout wave1b-installer`, `git stash pop`, затем commit.
3. Вернуть основную папку на `main` и закоммитить задания:
   ```
   git checkout main
   git add tasks/
   git commit -m "Wave 1 task files"
   ```
   Проверить: `git status` чистый, `git log --oneline --all`.
4. Создать worktree'ы:
   ```
   git worktree add C:\Users\gareg\Desktop\ThermoGar-w1a wave1a-unfreeze
   git worktree add C:\Users\gareg\Desktop\ThermoGar-w1b wave1b-installer
   git worktree add C:\Users\gareg\Desktop\ThermoGar-w1c wave1c-backend-tests
   ```
   В каждый worktree подтянуть задания: `git -C <wt> merge main` (fast-forward невозможен, обычный merge без конфликтов).
5. В worktree'ах НЕТ игнорируемых папок (`.venv-windows`, `_archive_codex`, `ThermoGar-Installer-Assets`, `dist`, `user_data`).
   Исполнители используют их по абсолютным путям из основной папки (см. правки в заданиях). `dist\` для 1B —
   создать в worktree свою (`C:\Users\gareg\Desktop\ThermoGar-w1b\dist`, игнорируется).
6. Отчёт: вывод `git worktree list` и `git log --oneline --all`.
