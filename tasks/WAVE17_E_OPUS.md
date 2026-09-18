Задача 17-Е — выпуск 0.4.2: слияние в main, тег, пуш. Санкция мастера на слияние — ДАНА, только этот раз.
Расчётов нет. В D:\Pets\Lilith не заходить.

ЧТО ПРОЧИТАТЬ: tasks/RULES.md; tasks/WAVE17_D_REPORT.md («Итог», «Git»); tasks/WAVE13_R_REPORT.md —
как оформлялось слияние и тег 0.4.1.

ДЕРЕВО. D:\Pets\ThermoGar, ветка wave15-release, вершина — коммит с отчётом 17-Д.

1. Предмержевая проверка: git status --short — ни одного M; git diff --stat main...wave15-release --
   databases пуст; app/thermogar_release_policy.py APP_VERSION = 0.4.2; CHANGELOG первый раздел
   «## 0.4.2 — 2026-09-18»; sha256 dist/release-0.4.2/ThermoGar-0.4.2-win64.exe =
   DF08800828B32F86CE1CD17BDA8EE1EC3B39A925F65520EB0B6993F09913D8EF. Расхождение — СТОП.
2. Реестр: строка «Выпуск 0.4.2 — 2026-09-18, тег v0.4.2» после таблицы волны 17, как у 0.4.1 в
   волне 13; строки 17-Д (принята), 17-Е (сдано); подраздел «Ошибка мастера (17-Д)»: запрет
   на Lilith был задан как правило, а не как исключение каталога из обхода — исполнитель прошёл по
   нему поиском makensis.exe, файлов не открывал. Коммит.
3. git checkout main; git merge --no-ff wave15-release -m "Merge wave15-release: release 0.4.2";
   конфликт — СТОП. git tag -a v0.4.2 -m "ThermoGar 0.4.2 — 2026-09-18". git push origin main;
   git push origin v0.4.2; git push origin wave15-release.
4. Проверка: git ls-remote --heads --tags origin — main на коммите слияния, v0.4.2 на месте.
5. Отчёт tasks/WAVE17_E_REPORT.md: хеш слияния, тега, вывод п. 4, git log --oneline -3 main.
   Промт сохранить как tasks/WAVE17_E_OPUS.md. Оба — в отдельный коммит на main после тега
   («docs(17-Е): отчёт») и запушить.
