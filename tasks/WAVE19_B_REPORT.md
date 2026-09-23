# Отчёт 19-Б: слияние 19-А в main и реестр

Исполнитель — Claude Opus 5.5, 23.09.2026, ноутбук Windows 10, `D:\Pets\ThermoGar`, `.venv-windows`.

## Итог

`wave19-a` влита в `main` коммитом `ef0643e`, проверки шага 1 пусты, число BL-58 сошлось (99 из 426), реестр исправлен и запушен коммитом `340deeb`.

## Шаг 0

Исходная ветка дерева — `wave19-a`. `git status --short`:

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? _to_delete/
?? results/wave17_b/
?? results/wave18_a/p4/log_density_base_fecrc_off.txt
?? results/wave18_a/p4/log_density_base_fecrc_on.txt
?? results/wave18_a/p4/log_density_base_nialcr_off.txt
?? results/wave18_a/p4/log_density_base_nialcr_on.txt
?? results/wave18_a/p4/log_density_base_nicr_off.txt
?? results/wave18_a/p4/log_density_base_nicr_on.txt
?? results/wave18_a/p4/log_density_head_fecrc_off.txt
?? results/wave18_a/p4/log_density_head_fecrc_on.txt
?? results/wave18_a/p4/log_density_head_nialcr_off.txt
?? results/wave18_a/p4/log_density_head_nialcr_on.txt
?? results/wave18_a/p4/log_density_head_nicr_off.txt
?? results/wave18_a/p4/log_density_head_nicr_on.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4/log_elastic_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off_r2.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_ctrl_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_on.txt
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```

Изменений в отслеживаемых файлах нет. `git fetch origin` без вывода.

```
e14b3e3e60bc35712c0c6d151582e5d7eda5d67d	refs/heads/main
05003794ed9a72fc63d4dc35f743fbc0c38f1c64	refs/heads/wave19-a
```

Обе головы совпали с заданием.

## Шаг 1

`git merge --ff-only origin/main`: `Already up to date.`, HEAD `e14b3e3e60bc35712c0c6d151582e5d7eda5d67d`.
`git merge --no-ff origin/wave19-a`: `Merge made by the 'ort' strategy.`, 46 files changed, 2298 insertions(+), 21 deletions(-). Коммит слияния `ef0643e` (<М>).

`git diff --stat origin/wave19-a HEAD`:

```
```

`git diff --stat e14b3e3 HEAD -- databases packaging CHANGELOG.md`:

```
```

Оба вывода пусты.

## Шаг 2

Файлы `results/wave19_a/posle/1v_phase_reference_{ni,al,fe}.csv`, pandas, все ячейки как строки (`dtype=str`, `keep_default_na=False`). Заглушка: «Описание по-русски» содержит «Русская расшифровка», и «Оригинал из базы (англ.)» после `strip` непустой.

| База | Заглушка при английском описании | Строк в CSV | Ожидание мастера |
|---|---|---|---|
| Ni | 28 | 99 | 28 / 99 |
| Al | 27 | 195 | 27 / 195 |
| Fe | 44 | 132 | 44 / 132 |
| всего | 99 | 426 | 99 / 426 |

Сошлось.

## Шаг 3

`tasks/REGISTER.md`, <М> = `ef0643e`: 3а — строка 19-А; 3б — строки BL-55 и BL-56 (по одному вхождению в каждой); 3в — строка BL-58, колонки «Что» и «Состояние»; 3г — подраздел «Ошибка мастера (19-А)» после «Ошибка мастера (BL-56, 19-А)», перед «## Завершённые волны». Тексты мастера вставлены дословно. Остальные строки не менялись: `git diff --stat` — 8 insertions(+), 4 deletions(-).

## Шаг 4

Коммит `340deeb`: `tasks/REGISTER.md` + `tasks/WAVE19_B_OPUS.md`. `git push origin main`: `e14b3e3..340deeb  main -> main`.

```
340deeb0239e3693909238ae4aa4f493100ea04f	refs/heads/main
```

## Отступления от задания

1. Строка BL-58, колонка «Состояние»: прежний текст кончался словом «источнике» без точки. Перед дописанным текстом мастера поставлены точка и пробел, иначе два предложения слились бы.
2. Подраздел 3г: между заголовком «### Ошибка мастера (19-А)» и абзацем вставлена пустая строка, как у остальных подразделов «Ошибка мастера» в реестре. Без неё текст тот же.
3. `tasks/WAVE19_B_OPUS.md`: первая строка вставленного текста `/caveman ultra` в файл не записана. Это команда режима ответа сессии, а не текст задания. Остальное — дословно.
4. `git log` и `git status` ниже сняты до коммита этого отчёта. Коммит отчёта в `git log` не входит, файл отчёта в `git status` не входит.
5. Шаг 2 запускал скрипт из временного каталога сессии, вне дерева. В дерево он не записан.

## git log --oneline e14b3e3..main

```
340deeb docs(19-Б): 19-А принята и влита в main, BL-58 — 99 фаз из 426
ef0643e Merge wave19-a: BL-55, BL-56 (19-А принята)
0500379 docs(19-А): ls-remote ветки в отчёте
7cbf67e docs(19-А): отчёт WAVE19_A_REPORT.md
06219d8 docs(19-А): реестр волны 19, BL-55/BL-56, ошибка мастера, правила; регрессия
37ef3d6 fix(19-А): BL-56 закрытый перечень режима стали; BL-55 ordered/disordered по слову
3f82bc6 test(19-А): тесты BL-56 и BL-55 до правки (красные на e14b3e3)
3194f66 test(19-А): замер ДО — цепочка режима стали, выпуски, справочник фаз, Fe–0,8C
142c49d docs(19-А): задание 19-А (BL-56, BL-55) дословно
```

## git status --short

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? _to_delete/
?? results/wave17_b/
?? results/wave18_a/p4/log_density_base_fecrc_off.txt
?? results/wave18_a/p4/log_density_base_fecrc_on.txt
?? results/wave18_a/p4/log_density_base_nialcr_off.txt
?? results/wave18_a/p4/log_density_base_nialcr_on.txt
?? results/wave18_a/p4/log_density_base_nicr_off.txt
?? results/wave18_a/p4/log_density_base_nicr_on.txt
?? results/wave18_a/p4/log_density_head_fecrc_off.txt
?? results/wave18_a/p4/log_density_head_fecrc_on.txt
?? results/wave18_a/p4/log_density_head_nialcr_off.txt
?? results/wave18_a/p4/log_density_head_nialcr_on.txt
?? results/wave18_a/p4/log_density_head_nicr_off.txt
?? results/wave18_a/p4/log_density_head_nicr_on.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4/log_elastic_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off_r2.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_ctrl_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_on.txt
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```
