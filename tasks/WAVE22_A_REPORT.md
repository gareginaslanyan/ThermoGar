# 22-А — отчёт: настольная оболочка, выпуск 0.6.0

Задание — запрос владельца: «мне не нравится веб-окно, хочется, чтобы у программы было своё
рабочее приложение без веб-окон». Ветка `wave22-tauri` от `c5dc9da` (`origin/main`). Дерево
`D:\Pets\ThermoGar`. Физика, базы и числа не затронуты.

**Итог.** Ярлык запускает `ThermoGar.exe` — оболочку на Tauri 2 (Rust, WebView2). Приёмка
`packaging/smoke_installed.ps1`: **8 из 8 PASS**, `dist/smoke-20261110T082013Z.json`.
Установщик `dist/ThermoGar-0.6.0-win64.exe`, 113,8 МБ, SHA-256
`33D257A74BD35592771099CC15EB570586C4C9B93F054F1412A0199BC47F2592`.

## Что сделано

1. **Оболочка `desktop/src-tauri`** (Rust, ~200 строк). Запускает прежний `launcher.pyw`,
   читает `ui_port` из `%LOCALAPPDATA%\ThermoGar\runtime\run.json`, проверяет
   `/_stcore/script-health-check` и открывает окно 1440×900 с заголовком ThermoGar.
   К уже работающему экземпляру подключается, второй не поднимает.
2. **Заставка и страница ошибки** (`desktop/src/index.html`, `error.html`). Разбор базы
   занимает 20–60 с; пустое окно читалось бы как зависание. Если порт не появился за 260 с,
   окно показывает причину и что проверить.
3. **`launcher.pyw` не тронут ни строкой.** Замок запуска, запись `run.json`, job-объект,
   проверки целостности установки и здоровья остались единственным источником правды о том,
   запущена ли программа. Оболочка не дублирует супервизор: два супервизора над одним
   процессом дали бы два источника правды.
4. **NSIS** (`packaging/ThermoGar.nsi`): ярлыки ведут на `ThermoGar.exe`, добавлена проверка
   его наличия наравне с рантаймом, деинсталлятор его удаляет.
5. **Поставка** (`packaging/stage_payload.ps1`): exe добавлен в `$SingleFiles` и в
   `$RequiredInStage`; без него стейджинг падает с `PAYLOAD_SOURCE_MISSING` — намеренно.
6. **Приёмка** (`packaging/smoke_installed.ps1`): шаг 3 и `Start-InstalledApp` запускают
   `ThermoGar.exe`, а не `pythonw launcher.pyw` — проверяется тот путь, которым идёт
   пользователь по ярлыку. `ThermoGar.exe` добавлен в список обязательных файлов.
7. **Версия 0.6.0**, `CHANGELOG.md`, `HANDOFF.md`, `THIRD_PARTY_NOTICES.txt` (перегенерация
   сборкой), `.gitignore` (`desktop/src-tauri/target/`).

## Дефект, найденный приёмкой и закрытый в этой же волне

Первый прогон: **7 из 8 PASS, шаг 7 FAIL** — после удаления оставался `ThermoGar.exe`.

Причина не в деинсталляторе. Оболочка ждала только `RunEvent::ExitRequested`, поэтому после
`stop.pyw` (и после удаления, которое останавливает приложение) окно продолжало жить,
показывая страницу от мёртвого процесса, и держало exe открытым. Три процесса `ThermoGar.exe`
висели 4 минуты; файл был залочен, `Delete` в деинсталляторе не срабатывал.

Исправлено (`b6a70c8`): оболочка следит за дочерним процессом раз в секунду и выходит, если
тот завершился сам. Повторный прогон — шаг 7 `leftover files 0`, на диске после прогона чисто:
ни папки, ни процессов, ни записи в реестре.

## Рантайм собран заново

Папка `ThermoGar-Installer-Assets\runtime-clean-3119` на машине отсутствовала; без неё
`stage_payload.ps1` падал с `RUNTIME_SOURCE_NOT_FOUND`, то есть установщик собрать было нечем.

Собран из embeddable CPython 3.11.9 (`python.org`, архив SHA-256 `009D6BF7…83CFD3B`) плюс
`get-pip.py`; `python311._pth` дополнен строкой `Lib\site-packages`. Версии пакетов выровнены
под эталонный `.venv-windows`; расхождение осталось только по тестовым (playwright,
pytest-timeout, greenlet, Markdown, pyee), в поставку они не идут.

## Приёмка, дословно

```
[PASS] step 1: silent install (43,4s)          installer exit 0
[PASS] step 2: files, shortcut, registry       missing=0 database=True shortcut=True registry=True version=0.6.0
[PASS] step 3: launcher started (3,4s)         pid=7420 alive=True
[PASS] step 4: healthcheck HEALTHY (67,5s)     ui_port=63935 control_port=63932
[PASS] step 5: UI 200, app script runs clean   GET / -> 200 (11141 bytes); script-health-check -> 200 'ok'
[PASS] step 6: stop: no processes, ports free  stop exit 0, remaining processes 0, ports free True
[PASS] step 7: silent uninstall                uninstaller exit 0, leftover files 0, registry gone True, LOCALAPPDATA kept True
[PASS] step 8: upgrade over existing install   project kept across upgrade True, identical True; uninstall removed True
OVERALL: PASS
```

## Отступления и замечания

1. **Тулчейн ставился с нуля.** На машине не было ни Rust, ни Node, ни MSVC. Поставлены:
   Rust 1.99.1 (rustup, профиль minimal), Node v24.19.0, MSVC BuildTools 17.14.44 с Windows SDK
   10.0.22621.0. Установщик MSVC попросил перезагрузку — для линковки она не понадобилась,
   сборка прошла.
2. **`Set-Content -Encoding UTF8` в PowerShell 5.1 пишет BOM**, и парсер Tauri его не принимает
   (`unable to parse JSON ... expected value at line 1 column 1`). Все файлы оболочки
   перезаписаны через `[IO.File]::WriteAllText` с `UTF8Encoding($false)`.
3. **`tauri::State` не подошёл**: guard заимствует app handle и переживает его в потоке и в
   колбэке события (`E0597`). Состояние держится в `Arc<Mutex<Option<Child>>>`.
4. **`tauri.conf.json`: `bundle.active = false`.** Установщик собирает NSIS, а не Tauri, поэтому
   встроенный бандлер не нужен; иконки нужны только для ресурса Windows.
5. **Подпись кода отсутствует** — решение владельца: «нет сертификата, пускай ругается».
   SmartScreen будет предупреждать.

## git

```
ed83073 release(22-A): THIRD_PARTY_NOTICES для 0.6.0 — перегенерация под собранный рантайм
b6a70c8 fix(22-A): оболочка выходит, когда лаунчер остановлен извне
6c4da54 feat(22-A): настольная оболочка на Tauri 2 — своё окно вместо вкладки браузера
```

Ветка `wave22-tauri` запушена в `origin`
(`https://github.com/gareginaslanyan/ThermoGar/pull/new/wave22-tauri`).