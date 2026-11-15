# ChronoSeal · HASH_REPORT_ENTERPRICE — Текущо състояние и работа на програмата

**Версия на пакета:** `5.4.0-rc1` (`package.json`)
**Дата на документа:** 2026-11-08
**Обхват:** описание на съществуващото състояние ПРЕДИ надграждането (v89).
Този документ не променя нищо в кода; той е базова линия за надграждането,
описано в `V89_UPGRADE_PLAN_BG.md`.

---

## 1. Предназначение

ChronoSeal създава юридически защитим „хеш отчет“ (PDF) за набор от файлове,
подпечатва го с два независими RFC 3161 времеви печата (START и STOP) и
съхранява пълно доказателство (evidence case), което може да бъде проверено
независимо от програмата.

Три са основните обещания на продукта:

1. **Пълен обхват** — отчетът не пропуска файл от избрания набор, освен ако
   изключването не е изрично разрешено и документирано.
2. **Независимост на времето** — времевите печати идват от външни TSA и се
   проверяват срещу одобрени доверителни вериги, а не срещу локален часовник.
3. **Възпроизводимост** — всеки SHA-256 в отчета може да бъде преизчислен
   върху реалните байтове на файловете.

---

## 2. Точки за стартиране

| Файл | Роля |
| --- | --- |
| `Start_ChronoSeal.bat` | Стартира `ChronoSeal_GUI.pyw` с `pythonw.exe`. Това е основният вход. |
| `ChronoSeal_GUI.pyw` | Единственият работен интерфейс (Tk). Зарежда legacy двигателя и automation панела. |
| `ChronoSeal_Original_Legacy.py` | Базов `App(tk.Tk)` клас: състояние, настройки, диагностика, `start()`/`worker()`. |
| `automation/Start_Automation.py` | Отделен панел „Automatic Reports“ с режими на планиране. |
| `automation/automation_core.py` | `plan()` / `execute()` — планиране и изпълнение на партиди. |
| `chronoseal/pipeline.py` | Оркестратор: preflight → generate → compose → stamp → verify → manifest. |
| `hash_report_generator/hash_report_combined.py` | Генератор за папка (COMBO отчет), стартира се като отделен процес. |
| `hash_report_generator/hash_report_single.py` | Генератор за един файл (SINGLE отчет). |
| `hash_report_generator/hash_report_core.py` | Обща база: хеширане, стилове, PDF секции, SQLite evidence. |
| `bootstrap.py` | Проверка на средата и (опционално) инсталиране на PySide6 за Qt варианта. |
| `desktop.py` | Qt (PySide6) вариант на интерфейса — **не се използва** от `Start_ChronoSeal.bat`. |
| `chronoseal_cli.py` | Команден ред, използва същия `Pipeline`. |

> **Важно:** `bootstrap.py` препраща към `start-new.pyw`, който липсва в
> дървото на проекта. Затова единственият работещ GUI е Tk приложението
> `ChronoSeal_GUI.pyw`. Всички тестове в v89 минават през него.

---

## 3. Архитектура на файловете

```
ChronoSeal_GUI.pyw            <- shell: header, rail, 4 страници, footer
  +-- ChronoSeal_Original_Legacy.py   <- App(tk.Tk): състояние + start/worker
        +-- chronoseal/pipeline.py    <- Pipeline.run()
              +-- subprocess: hash_report_generator/hash_report_combined.py
                    +-- hash_report_core.py (хешове, PDF, SQLite evidence)
  +-- automation/Start_Automation.py  <- втори панел (планиране)
        +-- automation/automation_core.py
```

`chronoseal/` (20 модула) покрива: `pipeline`, `settings`, `logging_bundle`,
`startup`, `provider_bootstrap`, `provider_catalog`, `qualified_validation`,
`trusted_lists`, `pdf_preflight`, `report_contract`, `report_quality`,
`report_archive`, `page_identity`, `storage_identity`, `unified_report_profile`,
`unified_theme`, `assembly_validation`, `selfheal`, `util`, `i18n`.

---

## 4. Работен поток на `Pipeline.run()`

`Pipeline.run(target, mode, recursive, include_explanation, include_source_pdf, output_dir)`

| Стъпка | Прогрес | Какво прави | Артефакт |
| --- | --- | --- | --- |
| 0 | 0 % | `preflight()` — проверка на вход, TSA политика, доверие, инструменти | startup отчет |
| 0 | 0 % | `inspect_storage()` — идентичност и свободно място на носителя | `storage-identity.json` |
| 0 | 0 % | `_make_case_dir()` — създава `ChronoSeal_Evidence/<време>_<hex>` | evidence case |
| 1 | 20 % | `generate()` — стартира генератора като дете | `*_HASHREPORT_TYP_SINGLE|COMBO.pdf` |
| 2 | 45 % | `_compose()` — независимо копие, page identity, приложения | `page-identity.json` |
| 3 | 45 % | `stamp()` — START + STOP RFC 3161, DSS, Certs | `rfc3161-audit.json` |
| 4 | 80 % | финална проверка след повторно отваряне на PDF | `layout-audit.json` |
| 5 | 100 % | `manifest.json`, архив, логове | `manifest.json` |

Публикуването е **транзакционно**: отчетът се сглобява в частния evidence
case и се премества под финалното име само след като START и STOP
подпечатванията и повторното отваряне минат. Частичен PDF никога не остава
под финално име.

### Имена на изхода

* файл -> `RPT-...-_HASHREPORT_TYP_SINGLE.pdf`
* папка -> `RPT-...-_HASHREPORT_TYP_COMBO.pdf`
* папка + recursive -> `..._COMBO_ALL.pdf`
* PDF с вграждане -> `..._SINGLE_PDF.pdf`

---

## 5. Генератор на отчети

### 5.1 Discovery (откриване на файлове)

`_discover_all_files_from_folder(folder_path, exclude_paths, recursive)`:

1. `_iter_evidence_files()` — детерминиран ред (сортиране по име, после по тип).
2. Не се слиза в symlink/junction директории, освен ако
   `CHRONOSEAL_FOLLOW_LINKS=1`; такива пътища се записват в `skipped_links`.
3. Пропускат се вече генерирани отчети (`_is_generated_hash_report`),
   `discovery-unreadable.json` и `hash_report_evidence.sqlite3*`.
4. Всеки файл се хешира с `calculate_sha256()` (3 опита при transient
   заключване, 8 KB блокове, проверка че файлът не е променен по време на четене).
5. Нечитаемите файлове **спират** изпълнението, освен ако
   `generator.allow_unreadable_files=true`; тогава се записват в
   `discovery-unreadable.json` и отчетът излиза с явен списък на изключванията.
6. Накрая се печата `Discovery audit: <път>` — **последният ред преди тишината**
   в проблемния сценарий.

### 5.2 Проверка преди генериране

`_verify_before_generate(files_info)` преизчислява SHA-256 на **всеки** файл
втори път и сравнява с първия резултат. Функцията не печата нищо.

### 5.3 Построяване на PDF

`generate(files_info, output_path, include_explanatory, report_identity)`:

* заглавна част (`report_header`), системна информация, START печат;
* таблица със 7 колони (№, файл, тип, KB, създаден, променен, SHA-256);
* обобщена статистика, END печат, правна декларация, футър;
* `doc.build(story, canvasmaker=NumberedCanvas)`;
* вграждане на RFC 3161 отговорите като PDF приложения;
* опционален `..._ERLAEUTERUNG.pdf`;
* запис в SQLite evidence база.

### 5.4 Класификация на типовете

`_classify_artifact_file()` + `_get_type_priority()` подреждат файловете по
значимост (ORIGINAL EML, PDF, изображения, архиви, опасно съдържание и т.н.).

---

## 6. Watchdog и бюджети

`Pipeline._run()` пази детето с два независими таймера:

| Таймер | Ключ в `config.json` | Стойност | Поведение |
| --- | --- | --- | --- |
| Абсолютен | `generator.timeout_seconds` | `0` = без лимит | убива след N секунди общо време |
| Тишина (idle) | `generator.idle_timeout_seconds` | `900` | убива след N секунди **без изход** |

Всеки ред от stdout/stderr на детето нулира idle таймера. Родителят печата
`... still running (Ns, N output lines)` на всеки 30 s, когато `stream=True`.

`_run()` чете двата канала през отделни drain нишки (без deadlock при голям
изход), а при спиране изтрива частичния PDF, за да не бъде взет за готов отчет.

---

## 7. RFC 3161 двойно подпечатване и доверие

Режим `DUAL-STAMP`, `SHA-512`, `enable_ltv=true`, `strict_ess=true`,
`require_distinct_providers=true`, `require_qualified_stop=true`.

| Етап | Доставчик | Транспорт | Доверие |
| --- | --- | --- | --- |
| START | FreeTSA | `https://freetsa.org/tsr` | `trust\FreeTSA\certificate-2.pem` |
| STOP | InfoNotary-QTSA (eIDAS qualified) | `http://ts.infonotary.com/tsa` | `trust\InfoNotary\qualified-root.pem` + intermediate |

Trusted List валидацията е вързана към ЕС LOTL (`trust\LOTL\eu-lotl.xml`,
подписващ сертификат с фиксиран SHA-256) и българския TSL (`tsl-bg.xml`).
Квалифицираният статус на STOP се доказва от TSL, не от името на доставчика.

---

## 8. Evidence case

```
ChronoSeal_Evidence/<YYYYmmdd_HHMMSS>_<12 hex>/
    discovery-unreadable.json     <- нечитаеми файлове + непрескочени връзки
    storage-identity.json         <- идентичност на носителя
    page-identity.json            <- съответствие страница -> секция
    source-pdf-signature-audit.json
    embedded-original.json
    rfc3161-audit.json            <- START/STOP, DSS, Certs, валидация
    layout-audit.json             <- READ ONLY проверка на оформлението
    manifest.json                 <- обобщен манифест на цялата операция
    hash_report_evidence.sqlite3  <- SQLite запис на отчета
    logs/                         <- пълният session лог
```

---

## 9. GUI (Tk) — `ChronoSeal_GUI.pyw`

Обвивка: заглавна лента с часовник и избор на език, лява навигационна релса,
`ttk.Notebook` без видими табове, футър.

| № | Страница | Атрибут | Съдържание |
| --- | --- | --- | --- |
| 01 | Report & TSA | `run_tab` | вход (файл/папка), „Include subfolders“, изход, бутон за пускане, прогрес, лог |
| 02 | Automation | `automation_tab` | `automation/Start_Automation.py` — режими и партиди |
| 03 | Settings & Trust | `set_tab` | архив, генератор, Node/OpenSSL, TSA профили, доверие |
| 04 | Diagnostics | `diag_tab` | preflight, диагностика, логове, evidence |

Навигация: `Ctrl+1` ... `Ctrl+4`, бутони в релсата, `<<NotebookTabChanged>>`.

### Пускане на отчет от главния панел

`App.start()`:

1. изисква `startup_ready`;
2. `_sync_input_mode()` — файл -> SINGLE, папка -> COMBO;
3. `askyesno` за ERLAEUTERUNG;
4. `askyesno` за PDF вграждане (само при избран `.pdf`);
5. `_run_args = (target, mode, recursive, explanation, source_pdf, output_dir)`;
6. `worker()` в отделна нишка -> `Pipeline.run(*_run_args)`.

### Език

`chronoseal/i18n.py`: `install()`, `tr()`, `translate()`, `set_language()`,
`add_language_selector()`, `on_change()`, `month_abbr()`. Низовете в
automation панела са на български по подразбиране.

---

## 10. Automation панел

`automation/Start_Automation.py` (`App`), режими от `automation_core.MODES`:

| Режим | Значение |
| --- | --- |
| `SINGLE_SELECTED` | отчет за един избран файл |
| `SINGLE_FOLDER` | по един отчет за всеки файл в папката |
| `COMBO_FOLDER` | един комбиниран отчет за папката |
| `COMBO_RECURSIVE` | един комбиниран отчет за папката и подпапките |
| `SINGLE_AND_COMBO` | и двете |
| `COMBO_SELECTED` | комбиниран отчет за избрани файлове |
| `SINGLE_AND_COMBO_SELECTED` | и двете за избрани файлове |

`plan(source, mode, selected)` връща списък задачи, `execute()` ги изпълнява
през същия `Pipeline.run()`.

---

## 11. Конфигурация (`config/config.json`)

| Ключ | Стойност | Значение |
| --- | --- | --- |
| `generator.package_dir` | `hash_report_generator` | къде е генераторът |
| `generator.combined_script` | `hash_report_combined.py` | COMBO генератор |
| `generator.single_script` | `hash_report_single.py` | SINGLE генератор |
| `generator.python` | `python` | интерпретатор на детето |
| `generator.output_glob` | `*.pdf` | как се разпознава нов отчет |
| `generator.timeout_seconds` | `0` | без абсолютен лимит |
| `generator.idle_timeout_seconds` | `900` | лимит на тишината |
| `generator.allow_unreadable_files` | `false` | fail-closed |
| `generator.follow_links` | `false` | без слизане по junctions |
| `rfc3161.mode` | `DUAL-STAMP` | START + STOP |
| `rfc3161.hash_algorithm` | `SHA-512` | алгоритъм на печатите |
| `rfc3161.timeout_seconds` | `3600` | мрежов бюджет |
| `archive.enabled` | `true` | архивиране на всеки отчет |
| `tools.node` / `tools.openssl` | пътища | външни инструменти |

---

## 12. Environment контракт към генератора

Генераторът е самостоятелен скрипт и получава политиката си **само** през
среда (без импорт на `chronoseal`):

| Променлива | Значение |
| --- | --- |
| `CHRONOSEAL_REPORT_ONLY` | `1` — ChronoSeal поема финалното DSS вграждане |
| `CHRONOSEAL_ALLOW_UNREADABLE_FILES` | `1` — разрешава изключвания с одит |
| `CHRONOSEAL_FOLLOW_LINKS` | `1` — слиза по връзки |
| `CHRONOSEAL_EVIDENCE_DIR` | къде да пише одитните JSON файлове |
| `CHRONOSEAL_INCLUDE_EXPLANATION` | `1` — отделен ERLAEUTERUNG PDF |
| `CHRONOSEAL_TSA_TRUST_ROOTS` | JSON списък с доверителни сертификати |
| `CHRONOSEAL_TSA_INTERMEDIATES` | JSON списък с междинни сертификати |
| `CHRONOSEAL_VOLUME_JSON` | JSON с идентичността на носителя |
| `PYTHONIOENCODING`, `PYTHONUTF8`, `PYTHONUNBUFFERED` | UTF-8 и небуфериран изход |

---

## 13. Тестове

| Команда | Обхват |
| --- | --- |
| `npm test` | `tests/` (46 модула) + `hash_report_generator/tests/` (34 модула) |
| `npm run check` | `node --check bridge/stamp.mjs` |
| `npm run verify:vendor` | цялост на `vendor/pdf-rfc3161` |
| `npm run selfcheck` | `python -m chronoseal.selfheal` |
| `npm run doctor` | проверка на `pdf-rfc3161` |
| `npm run verify` | всичко изброено, последователно |

Съществуващи тестове, близки до тази задача:
`tests/test_pipeline_watchdog.py`, `tests/test_hardening.py`,
`tests/test_recursion_semantics.py`,
`tests/test_explicit_file_selection_source.py`,
`hash_report_generator/tests/test_unreadable_evidence_v93.py`.

---

## 14. Известен дефект във v5.4.0 — „тих“ генератор

**Симптом.** След `Discovery audit: ...\discovery-unreadable.json` програмата
спира да произвежда какъвто и да е изход. След 900 s watchdog-ът убива
детето и потребителят вижда:

```
PipelineError: Child process stalled: no output for 900s: hash_report_combined.py
```

**Причина.** Следващата стъпка след discovery е
`_verify_before_generate()`, която **преизчислява SHA-256 на всички файлове
втори път** и не печата нищо. Върху голямо дърво (40 667 реда discovery изход)
на мрежов дял това надхвърля 900 s. Watchdog-ът е коректен — убива процес,
който наистина мълчи. Дефектът е в **липсата на прогрес**, не в таймера.

Следващите тихи фази са: построяване на таблицата с 40 000+ реда,
`doc.build()`, вграждане на RFC 3161 отговорите и записът в SQLite.

**Последствия.** Отчетът не се създава, evidence case остава частичен,
операторът не може да различи „бавно“ от „заклещено“.

**Решение.** Виж `V89_UPGRADE_PLAN_BG.md` — прогресивен heartbeat, който
доказва активност по време на всяка дълга фаза, плюс диагностика в родителя
кой последен ред е видян.

---

## 15. Ограничения и бележки

* Мрежов дял (`\\PASEVCLAUD\HDD`) е бавен; `Get-ChildItem -Recurse` отнема
  над 30 s. Всички бюджети трябва да са съобразени с това.
* `desktop.py` (Qt) не е свързан с `Start_ChronoSeal.bat` и не се тества в v89.
* Git хранилището няма настроен remote; историята е локална.
* Генерираните отчети, evidence, архив, логове и виртуалната среда **не** се
  включват в резервното копие.
