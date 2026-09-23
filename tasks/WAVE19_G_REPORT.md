# Отчёт 19-Г: слияние 19-В и 19-В2 в `main`, реестр

**Итог:** `wave19-v2` (с `wave19-v`) влита в `main` коммитом `65aade0`, все проверки шага 1 чистые; реестр обновлён (19-В, 19-В2, BL-58, новый BL-59) коммитом `e599e50`, пуш сделан; замер шага 2 сошёлся с ожиданием: 123 CSV с `i/crlf`, 1151 с `i/lf`.

## Шаг 0

До начала работы дерево стояло на ветке `wave19-v2`. `git config core.autocrlf` — `true`.

`git status --short` (изменений в отслеживаемых нет, только неотслеживаемые):

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

`git fetch origin` — без вывода. `git ls-remote origin main wave19-v2`:

```
dd2f13dfb27fcce3e297276327033290a8a2ad70	refs/heads/main
81a746c97c088544f770731418f4786c9c598da5	refs/heads/wave19-v2
```

Оба хэша равны заданным.

## Шаг 1

`git checkout main` — `Switched to branch 'main'`, `Your branch is up to date with 'origin/main'.`; `git merge --ff-only origin/main` — `Already up to date.`, HEAD `dd2f13dfb27fcce3e297276327033290a8a2ad70`.
`git merge --no-ff origin/wave19-v2 -m "Merge wave19-v2: BL-58 (19-В и 19-В2 приняты)"` — `Merge made by the 'ort' strategy.`, 38 files changed, 3516 insertions(+), 1 deletion(-); коммит слияния `65aade0`.

Проверки:

```
$ git diff --stat origin/wave19-v2 HEAD
$ git diff --stat dd2f13d HEAD -- databases packaging CHANGELOG.md
$ git merge-base --is-ancestor 70616e2 HEAD && echo yes || echo no
yes
```

Первые два вывода пустые, `70616e2` — предок HEAD.

## Шаг 2

Коммит `dd2f13d`, `git ls-files --eol -- "*.csv"` по индексу, собранному из дерева `dd2f13d` (см. отступление 1):

| `i/` | число CSV |
|---|---|
| `i/crlf` | 123 |
| `i/lf` | 1151 |
| всего | 1274 |

Сверка с ожиданием 123 и 1151 — совпало. Перекрёстная проверка по блобам (`git ls-tree -r dd2f13d` + `git cat-file -p`, подсчёт CRLF и одиночных LF): 123 crlf, 1151 lf, 0 mixed, 0 none; всего `*.csv` в дереве 1274 (с учётом регистра и без — одинаково).

## Шаг 3

`tasks/REGISTER.md`, `<М>` = `65aade0`, `<N_crlf>` = 123, `<N_lf>` = 1151. Правки 3а, 3б, 3в — заменой ровно одного вхождения в своей строке (каждое вхождение проверено на единственность), остальной текст строк не менялся; 3г — строка BL-59 вставлена сразу после BL-58. Итог `git diff --stat`: 1 файл, 4 вставки, 3 удаления. Концы строк файла (LF) сохранены.

Строка `app/ThermoGar_app.py:5668-5671` на `65aade0` — это `return (` с текстом заглушки «Русская расшифровка для этой специализированной фазы ещё не добавлена.», ссылка 3в верна.

## Шаг 4

Коммит `e599e50` «19-Г: реестр после слияния 19-В и 19-В2, BL-59; задание 19-Г» — `tasks/REGISTER.md` + `tasks/WAVE19_G_OPUS.md`. `git push origin main` — `dd2f13d..e599e50  main -> main`.

```
$ git ls-remote origin main
e599e5006cfb336cb5b4ef6ae2e8af56ce76bc45	refs/heads/main
```

Отчёт — следующим коммитом.

## Отступления от задания

1. Шаг 2 выполнен не через временный worktree, а через временный индекс: `GIT_INDEX_FILE=results/wave19_g/tmp/index_dd2f13d git read-tree dd2f13d`, затем `git ls-files --eol -- "*.csv"` с тем же индексом. Причина: результат по столбцу `i/` тот же (он берётся из блобов), но рабочие файлы не выписываются на диск и не остаётся регистрации worktree в `.git/worktrees`. Числа подтверждены вторым способом (`git ls-tree` + `git cat-file`). Временные файлы (`index_dd2f13d`, `eol_dd2f13d.txt`) перенесены в `_to_delete/19g_tmp/`, опись `_to_delete/19g_tmp/SHA256SUMS.txt`:
   ```
   a54a26b0b740955a70a626702f9762c5f6b1a017ed26887f7c1bf12febd7aa55 *eol_dd2f13d.txt
   7b94d90fa38e87e785f69fe2053dbceddaa223d086b7bf81bdfca62dab546d0d *index_dd2f13d
   ```
   Пустые каталоги `results/wave19_g/tmp` и `results/wave19_g` удалены (`rmdir`); в них ничего, кроме этих двух файлов, не было.
2. `tasks/WAVE19_G_OPUS.md`: в присланном тексте задание предварялось строкой `/caveman ultra` — это команда режима ответов исполнителю, не текст задания; в файл не вошла. Текст с «Задание 19-Г: …» до конца сохранён дословно.
3. `git log --oneline dd2f13d..main` и `git status --short` ниже сняты после коммита `e599e50` и пуша, до коммита этого отчёта; сам коммит отчёта в них не виден.

## `git log --oneline dd2f13d..main`

```
e599e50 19-Г: реестр после слияния 19-В и 19-В2, BL-59; задание 19-Г
65aade0 Merge wave19-v2: BL-58 (19-В и 19-В2 приняты)
81a746c docs(tasks): add wave 19-V2 report
b3c5bd1 docs(register): accept 19-V, add 19-V2 row, close BL-58, owner texts, master error 19-V
365a29e results(wave19-v2): phase reference after change, comparison, green test
def1f49 feat(app): phase reference uses stub keys table instead of placeholder (BL-58)
7df3252 feat(phase-descriptions): add approved phrases and stub keys table (BL-58)
515210b test(phase-descriptions): stub keys table test, red before change (BL-58)
4f28746 results(wave19-v2): phase reference before change (step 1)
3fb47fd docs(tasks): add wave 19-V2 task
70616e2 docs(tasks): add wave 19-V report
7db5df9 docs(register): add 19-V row, move BL-58 to in progress
a900fcc results(wave19-v): Jev key markup (jev-1.13.0, 80 requests) and comparison
85c5810 results(wave19-v): phase list (99) and executor key markup (80 pairs)
863b526 docs(tasks): add wave 19-V task (BL-58 part 1, phase key markup)
```

## `git status --short`

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
