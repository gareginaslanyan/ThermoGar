# MERGE_WAVE1.ps1 — довести мержи волны 1 в main. Запуск на Windows из корня репо:
#   cd C:\Users\gareg\Desktop\ThermoGar
#   powershell -ExecutionPolicy Bypass -File tasks\MERGE_WAVE1.ps1
# Останавливается на первой неожиданной ошибке. Ничего не удаляет с диска, только из индекса git.
$ErrorActionPreference = 'Stop'
$env:GIT_OPTIONAL_LOCKS = '0'
Set-Location 'C:\Users\gareg\Desktop\ThermoGar'

function Run($cmd) { Write-Host ">> $cmd" -ForegroundColor Cyan; iex $cmd; if ($LASTEXITCODE -ne 0) { throw "FAILED: $cmd" } }

# 0. Снять зависший мерж и мусорный lock
if (Test-Path .git\index.lock) { Remove-Item -Force .git\index.lock }
if (Test-Path .git\MERGE_HEAD) { git merge --abort }
git checkout main
$st = git status --porcelain
if ($st) { throw "Рабочее дерево main не чистое после abort — покажи git status и остановись" }
Write-Host "main чистый:"; git log --oneline -1

# 1. Мерж 1B. Конфликты будут только в _archive_codex (rename/delete) — решаем, убирая _archive_codex из индекса.
Write-Host "`n=== merge wave1b-installer ===" -ForegroundColor Yellow
git merge --no-ff --no-commit wave1b-installer 2>&1 | Out-Host
# Убрать из индекса всё, что попало под _archive_codex (на диске остаётся, .gitignore его игнорирует)
git rm -r --cached --ignore-unmatch _archive_codex 2>&1 | Out-Null
# Проверить, что не осталось неразрешённых конфликтов вне _archive_codex
$unmerged = git diff --name-only --diff-filter=U
if ($unmerged) { throw "Остались конфликты вне архива:`n$unmerged`nОстановись и покажи." }
git commit -m "Merge wave 1B: installer pipeline without Codex gates, real smoke, launcher shutdown fixes`n`nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01M4C5gQx9cJ2PLg2Di7MpMc"
if (git ls-files _archive_codex) { throw "_archive_codex всё ещё в git — останови и покажи git ls-files _archive_codex" }
Write-Host "1B смержена, _archive_codex не трекается" -ForegroundColor Green

# 2. Мерж 1C (только новые файлы tools\, конфликтов быть не должно)
Write-Host "`n=== merge wave1c-backend-tests ===" -ForegroundColor Yellow
git merge --no-ff wave1c-backend-tests -m "Merge wave 1C: backend calculation matrix for Ni/Al/Fe`n`nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01M4C5gQx9cJ2PLg2Di7MpMc"

# 3. Зарегистрировать маркер pytest slow
if (-not (Test-Path tools\conftest.py)) {
@'
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: длительные расчёты диаграмм")
'@ | Set-Content -Encoding UTF8 tools\conftest.py
  git add tools\conftest.py
  git commit -m "Register pytest slow marker`n`nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`nClaude-Session: https://claude.ai/code/session_01M4C5gQx9cJ2PLg2Di7MpMc"
}

# 4. Проверка: приложение импортируется, ключевые тесты зелёные, установщик на месте
$py = 'C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe'
Write-Host "`n=== verify ===" -ForegroundColor Yellow
Run "& '$py' -I -B -X utf8 tools\thermogar_self_test.py --project-root C:\Users\gareg\Desktop\ThermoGar"
Run "& '$py' -I -B -X utf8 tools\thermogar_verified_loaders_test.py"
if (-not (Test-Path packaging\smoke_installed.ps1)) { throw "packaging\smoke_installed.ps1 отсутствует после мержа 1B" }
if (-not (Test-Path tools\test_backend_calculations.py)) { throw "tools\test_backend_calculations.py отсутствует после мержа 1C" }

Write-Host "`n=== DONE ===" -ForegroundColor Green
git log --oneline -8
Write-Host "`nПод git в _archive_codex (должно быть пусто):"; git ls-files _archive_codex
