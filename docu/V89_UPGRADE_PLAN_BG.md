# ChronoSeal · HASH_REPORT_ENTERPRICE — План за надграждане v89

**Базова версия:** `5.4.0-rc1`
**Целева версия:** `5.5.0`
**Дата:** 2026-11-08
**Базова линия:** `V89_CURRENT_STATE_BG.md`

> Този документ е планът, който се изпълнява след него. Нищо от съществуващото
> поведение не се премахва и не се пренаписва — само се надгражда.

---

## 1. Цели

| # | Цел | Критерий за успех |
| --- | --- | --- |
| G1 | Отстраняване на „тихия генератор“ | Нито една фаза на генератора не мълчи повече от `heartbeat_seconds` (по подразбиране 30 s) |
| G2 | Нов отделен панел за избор на папка с верижни файлови филтри | Панел `05 Selection`, идентичен избор на папка + подпапки като главния, плюс верижни филтри |
| G3 | Запазване на съществуващото състояние | Всички стари тестове минават; нефилтриран отчет е байтово еквивалентен по съдържание |
| G4 | Пълна документираност | Този документ + `V89_UI_TEST_REPORT_BG.md` |
| G5 | Резервно копие и релиз | Baseline архив в GitHub release ПРЕДИ имплементация; обновен архив след тестовете |

### Ограничения

* Не се променят: форматът на PDF таблицата, броят страници при нефилтриран
  отчет, схемата на `manifest.json` (само нови незадължителни полета),
  алгоритмите за хеширане, TSA политиката.
* Не се пипа `desktop.py` (Qt) — не се използва от стартовия `.bat`.
* Генераторът остава самостоятелен скрипт: комуникацията с него е **само**
  през среда и аргументи.

---

## 2. Причина за дефекта (затвърдена)

От лога `logs/session_20261108_034303_334969/`:

```
... Discovery audit: ...\ChronoSeal_Evidence\20261108_034334_78b7cdc9a8da\discovery-unreadable.json
<тишина 900 s>
Watchdog: child process produced no output for 900s; terminating process tree...
PipelineError: Child process stalled: no output for 900s: hash_report_combined.py
```

Верига на извикване:

```
ChronoSeal_Original_Legacy.worker()
  -> Pipeline.run()
    -> Pipeline.generate()
      -> Pipeline._run(idle_timeout=900, stream=True)
        -> hash_report_combined.py <folder>
          -> _discover_all_files_from_folder()   [печата по ред на файл]
          -> _write_unreadable_audit()           [последен печатан ред]
          -> _verify_before_generate()           [<-- ПЪЛНА ТИШИНА, re-hash на всичко]
          -> generate()                          [тиха подготовка на 40k реда таблица]
             -> doc.build()                      [тихо, минути]
             -> _embed_rfc3161_responses_in_pdf()[тихо]
             -> _save_sqlite_evidence_database() [тихо]
```

`_verify_before_generate()` е `for file_info in files_info: calculate_sha256(...)`
без нито един `print`. При 40 667 реда discovery изход и мрежов дял това е
над 900 s. **Watchdog-ът работи правилно; липсва прогрес.**

Допълнителен дефект: съобщението за грешка не казва коя фаза е била активна,
затова операторът не може да разбере дали проблемът е в I/O, в ReportLab или
в TSA.

---

## 3. Решение 1 — прогресивен heartbeat (G1)

### 3.1 Нов модул `hash_report_generator/progress_heartbeat.py`

Само стандартна библиотека (`os`, `sys`, `threading`, `time`). Без зависимости
от `chronoseal`, за да остане генераторът самостоятелен.

```python
class Heartbeat:
    def __init__(self, interval=None, stream=None): ...
    def start(self); def stop(self)
    def __enter__/__exit__
    def set_phase(self, phase, total=None)      # печата веднага
    def tick(self, done=None, note=None)        # брояч, без I/O
    def note(self, text)                        # печата веднага
    def snapshot(self) -> dict                  # phase, done, total, elapsed
```

Фонов режим: нишка печата на всеки `interval` секунди, ако е минало повече от
половината интервал от последния ред. Формат (ASCII, за да не се счупи на
cp1251/cp437 конзола):

```
[heartbeat] phase=verify done=8123/40667 elapsed=142s rate=57.2/s eta=569s
```

`interval` идва от `CHRONOSEAL_HEARTBEAT_SECONDS` (по подразбиране `30`,
`0` изключва). Модулен singleton `get()` / `phase()` / `tick()` / `note()` /
`close()` за удобство в големите файлове.

### 3.2 Точки на свързване

| Файл | Функция | Фаза | Брояч |
| --- | --- | --- | --- |
| `hash_report_combined.py` | `generate_from_folder` | `discovery` / `verify` / `pdf` | файлове |
| `hash_report_combined.py` | `_discover_all_files_from_folder` | `discovery` | файлове |
| `hash_report_core.py` | `_verify_before_generate` | `verify` | файлове |
| `hash_report_combined.py` | `generate` (таблица) | `table` | редове |
| `hash_report_combined.py` | `generate` (`doc.build`) | `pdf-build` | - |
| `hash_report_core.py` | `_embed_rfc3161_responses_in_pdf` | `embed` | артефакти |
| `hash_report_core.py` | `_save_sqlite_evidence_database` | `sqlite` | - |
| `hash_report_core.py` | `_get_rfc3161_timestamp` | `tsa` | - |
| `hash_report_single.py` | съответните | същото | 1 файл |

Всяко извикване на `set_phase()` печата ред **веднага**, което нулира idle
таймера на родителя. `tick()` е само брояч — нулева цена на файл.

### 3.3 Промени в родителя (`chronoseal/pipeline.py`)

1. `generator.heartbeat_seconds` (по подразбиране `30`) се предава като
   `CHRONOSEAL_HEARTBEAT_SECONDS`.
2. `Pipeline._run()` пази последните 8 реда от изхода и последната
   `[heartbeat] phase=...` стойност.
3. При idle спиране съобщението става:

```
Child process stalled: no output for 900s: hash_report_combined.py
  last phase: verify 8123/40667
  last output:
    [heartbeat] phase=verify done=8123/40667 elapsed=142s
    ...
```

4. Защита: ако `idle_timeout` е по-малък от `3 * heartbeat_seconds`, се логва
   предупреждение, че бюджетът е твърде тесен (не се променя автоматично).

### 3.4 Гаранции

* Никаква промяна в SHA-256 стойностите, реда на файловете, съдържанието на
  PDF или evidence JSON — heartbeat пише само на stdout.
* При `CHRONOSEAL_HEARTBEAT_SECONDS=0` поведението е точно като v5.4.0.

---

## 4. Решение 2 — панел за избор на папка с верижни филтри (G2)

### 4.1 Позиция

Нов запис в `NAV_ITEMS`: `("filter_tab", "05", "Selection & Filters",
"Pick a folder and filter by file type")`, страница `filter_tab` в `self.nb`,
`Ctrl+5`. Класът е в отделен файл `automation/File_Filter_Panel.py`
(зарежда се с `SourceFileLoader`, както automation панелът) — така
`ChronoSeal_GUI.pyw` остава четим.

### 4.2 Съдържание на панела

```
 1 · Folder            [ entry .......................... ] [Choose folder]
                       [x] Include subfolders

 2 · File type filters
     Filter 1  [ *eml.pdf                ]  (x)
     Filter 2  [ *.eml                   ]  (x)
     Filter 3  [                          ]        <- появява се автоматично
     Всяко поле е отделен филтър. Може и с запетая: *.pdf, *.eml
     [Clear filters]                      Активни филтри: 2

 3 · Preview
     Намерени: 1 284 файла · 312.4 MB · 0 нечитаеми
     [table: Относителен път | Тип | Размер KB]
     [Scan now] [Copy list]

 4 · Actions
     [Apply to main panel]  [Generate report from selection]
```

### 4.3 Семантика на филтрите

* Едно поле = един филтър. Запетава/точка и запетая в едно поле = няколко
  филтъра в едно поле (еквивалентно).
* Филтрите се комбинират с **ИЛИ** (файл се включва, ако съвпадне с поне един).
* Съвпадението е **glob, без значение от регистъра**, върху:
  * името на файла (`*.eml`), и
  * относителния път от избраната папка (`invoices/*/*.pdf`).
* `*eml.pdf` означава „всичко, което завършва на `eml.pdf`“ — точно както
  очаква потребителят.
* Празен списък = без филтър (всички файлове), т.е. старото поведение.
* `?` съвпада с един символ; `[abc]` — набор; `**` не се поддържа (няма нужда,
  защото `*` вече пресича `/` в нашия matcher).
* Файловете, изключени от филтъра, **не** са „нечитаеми“ — те са извън обхвата
  и се броят отделно.

### 4.4 Верижно добавяне на поле

`trace_add('write')` на `StringVar` на всяко поле: щом последното поле
получи непразен текст, веднага се създава ново празно поле и фокусът остава
при потребителя. Празните полета не се показват като филтри. Ред с `(x)`
премахва филтъра; първото поле не може да бъде премахнато (само изчистено).

### 4.5 Разпространение на филтрите

```
FilterPanel.collect_filters()  -> list[str]
        |
        v
App.file_filters (списък в главния App)
        |
        v
App._run_args = (..., filters)
        |
        v
Pipeline.run(..., filters=[...])
        |
        v
env CHRONOSEAL_INCLUDE_PATTERNS = JSON list
        |
        v
hash_report_combined._discover_all_files_from_folder()
```

### 4.6 Логични добавки, които НЕ могат да бъдат пропуснати

| # | Добавка | Защо е задължителна |
| --- | --- | --- |
| A1 | `hash_report_generator/file_filters.py` — `normalize()`, `parse()`, `matches()`, `describe()` | Една единствена реализация за GUI и генератор; иначе двете страни ще броят различно |
| A2 | `discovery-unreadable.json` получава `filters`, `excluded_by_filter_count` | Обхватът трябва да е възпроизводим от доказателството |
| A3 | `manifest.json` получава `selection_filters` | Одитът на операцията трябва да казва какво е избирано |
| A4 | PDF системна информация: ред `Selection filter:` **само** когато има активни филтри | Иначе подписаният отчет не казва, че е частичен |
| A5 | Грешка `FILTER_MATCHED_NO_FILES` с ясно съобщение | Иначе потребителят вижда „няма нов PDF“ |
| A6 | Филтърът не изключва защитените файлове по-рано от `_is_generated_hash_report()` | Генерираните отчети и evidence файловете остават извън обхвата независимо от филтъра |
| A7 | `recursive` и филтърът работят независимо | Комбинацията „подпапки + *.pdf“ е основният сценарий |
| A8 | Филтрите се пазят при превключване на страници и при `Apply to main panel` | Иначе изборът се губи |
| A9 | Индикатор в главния панел: `Selection filters: none | *.pdf, *.eml` + бутон `Clear` | Операторът трябва да вижда, че отчетът е частичен |
| A10 | `config.json`: `generator.heartbeat_seconds`, `generator.filter_case_sensitive=false` | Конфигурируемост без код |
| A11 | i18n низове за новия панел | Панелът трябва да следва езика на приложението |
| A12 | Документация + README раздел | Изискване на потребителя |
| A13 | Тестове само през UI | Изискване на потребителя |

### 4.7 Обратна съвместимост

| Сценарий | v5.4.0 | v5.5.0 |
| --- | --- | --- |
| Главен панел, без филтри | COMBO за всички файлове | същото |
| Automation панел | без филтри | същото (поле за филтри не се добавя) |
| CLI `chronoseal_cli.py` | без филтри | същото, `--filter` е опционален |
| `CHRONOSEAL_HEARTBEAT_SECONDS=0` | - | точно старото поведение |
| Стар `manifest.json` | без `selection_filters` | новото поле е незадължително |

---

## 5. План за тестове (само през UI)

Всички тестове стартират `ChronoSealDesktop(auto_bootstrap=False)` и работят
**само** с джаджи (entry, checkbox, button `.invoke()`, `StringVar.set`),
диалозите се заместват с детерминирани отговори. Нито един тест не вика
`Pipeline` или генератора директно.

| # | Сценарий |
| --- | --- |
| T01 | Панелът съществува, навигацията е 5 страници, `Ctrl+5` работи |
| T02 | „Choose folder“ (заменен диалог) записва пътя в полето |
| T03 | „Include subfolders“ по подразбиране е изключен |
| T04 | Въвеждане в първото поле създава второ поле веднага |
| T05 | Въвеждане във второто поле създава трето |
| T06 | Изтриване на текста не създава нови полета |
| T07 | „(x)“ премахва поле и филтъра му |
| T08 | Запетая в едно поле дава два филтъра |
| T09 | `*eml.pdf` съвпада с `scan_0001.eml.pdf` |
| T10 | Филтърът е без значение от регистъра |
| T11 | Няколко филтъра се комбинират с ИЛИ |
| T12 | Без филтър се показват всички файлове |
| T13 | С „подпапки“ резултатът включва вложените файлове |
| T14 | Без „подпапки“ вложените файлове липсват |
| T15 | Празен резултат показва съобщение, не изключение |
| T16 | „Apply to main panel“ пренася папка + подпапки + филтри и превключва на 01 |
| T17 | Главният панел показва активните филтри |
| T18 | „Clear“ в главния панел изчиства филтрите |
| T19 | „Generate report from selection“ подава филтрите към `Pipeline.run` |
| T20 | Празна папка при генериране дава ясно съобщение, без subprocess |
| T21 | Несъществуваща папка дава ясно съобщение |
| T22 | Сканирането не блокира UI (прогрес/статус се обновява) |
| T23 | Отказ от сканиране не оставя работеща нишка |
| T24 | Смяна на езика не чупи панела |
| T25 | Regression: главният панел пуска отчет без филтри (args без филтри) |
| T26 | Regression: automation панелът все още се зарежда и планира |
| T27 | Heartbeat: генератор, който спи > idle, но пише heartbeat, **не** бива убит |
| T28 | Heartbeat: генератор, който мълчи > idle, бива убит с ясно съобщение |
| T29 | Съобщението за спиране съдържа последната фаза |
| T30 | `CHRONOSEAL_HEARTBEAT_SECONDS=0` изключва heartbeat-а |

T27/T28 минават през UI бутона за пускане с временен конфиг, който сочи към
тестов генератор; те доказват поправката end-to-end.

**Правило при провал:** при първи неуспешен тест се стартира ЦЕЛИЯТ набор
отначало; така до 100 % минаване. Всяка итерация се записва в
`V89_UI_TEST_REPORT_BG.md` (итерация, брой минали/неуспешни, причина, корекция).

---

## 6. Ред на изпълнение

1. Този план + `V89_CURRENT_STATE_BG.md` (готово).
2. Резервно копие -> GitHub release `PasevSU/HASH_REPORT_ENTERPRICE`.
3. `progress_heartbeat.py` + свързване + диагностика в родителя.
4. `file_filters.py` + филтриране в генератора + `Pipeline.run(filters)`.
5. `automation/File_Filter_Panel.py` + навигация `05` + индикатор в главния панел.
6. UI тестове до 100 %.
7. `V89_UI_TEST_REPORT_BG.md` + README.
8. Обновяване на release-а с новия архив.

---

## 7. Откат

Всяка стъпка е отделна и независима:

* heartbeat — изключва се с `CHRONOSEAL_HEARTBEAT_SECONDS=0`;
* филтри — липсата на `CHRONOSEAL_INCLUDE_PATTERNS` връща старото поведение;
* панел — премахва се един запис от `NAV_ITEMS` и един `SourceFileLoader`.

Baseline архивът в release-а е пълната точка за възстановяване.

---

## 8. Статус на изпълнението (v5.5.0)

Всички 13 задължителни добавки (A1–A13) са налични в кода, плюс A14
(производителност, добавен след анализа `V90_JS_CAPABILITY_ANALYSIS_BG.md`). Проверката е правена срещу
реалните файлове, не срещу плана.

| # | Къде е реализирано | Статус |
| --- | --- | --- |
| A1 | `hash_report_generator/file_filters.py` | готово |
| A2 | `discovery-unreadable.json` -> `filters`, `excluded_by_filter_count` | готово |
| A3 | `manifest.json` -> `selection_filters` | готово |
| A4 | `hash_report_core.py` -> ред `Selection filter:` само при активни филтри | готово |
| A5 | `FILTER_MATCHED_NO_FILES` (код 3) в генератора и в панела | готово |
| A6 | филтърът се прилага след `_is_generated_hash_report()` | готово |
| A7 | `recursive` и филтрите са независими параметри | готово |
| A8 | `file_filters` живее в главния обект, оцелява смяна на страница | готово |
| A9 | индикатор `File type filter:` + `Clear` + `Edit in Selection` | готово |
| A10 | `config.json`: `heartbeat_seconds`, `filter_case_sensitive` | готово |
| A11 | 33 нови записа в `chronoseal/i18n.py` + `ttk.Treeview.heading` + `i18n.tr()` шаблони за динамичните редове | готово |
| A12 | `README.md` (раздел v5.5) + трите документа в `docu/` | готово |
| A13 | `tests/test_ui_selection_filters.py` — само през Tk джаджи | готово |
| A14 | R1/R2 — `hash_report_generator/js_rules_runner.cjs`, `js_rules.py`, `style_loader.py` | готово |

### 8.1 Какво беше добавено при A11

* 33 нови 3-ки `(English, Deutsch, Български)` в `CATALOG` — етикети на панела,
  помощния текст на филтрите, заглавията на колоните в прегледа, редовете за
  състояние и индикаторът в главния панел.
* `ttk.Treeview.heading` вече се локализира при създаване **и** при смяна на
  езика в движение (`apply_language()` обхожда колоните на всяко дърво).
* Динамичните редове се строят с шаблони, а не с конкатенация, за да не се
  превежда името на файла:

  ```python
  self.status.set(i18n.tr("Scanning {path}", path=target))
  self.status.set(i18n.tr("Scanned {count} candidate file(s).", count=len(entries)))
  ```

  Това е задължително, защото `i18n.install()` обвива `tk.StringVar.set` с
  `translate()`, а `translate()` разделя текста на `": "` и превежда главата.
  При конкатенация `"Scanning " + target` шаблонът не може да се приложи.

### 8.3 A14 — производителност без промяна на резултата

Анализът в `docu/V90_JS_CAPABILITY_ANALYSIS_BG.md` показа, че **единственият**
подходящ за пренасяне в JavaScript компонент е зареждането на JS правилата —
защото правилата вече са JS и Python само повтаряше файловите проверки, които
Node прави след това.

| Стъпка | Преди | След |
| --- | --- | --- |
| `read_js_rules` (32 файла, SMB) | 31.87 s | **13.67 s** |
| `read_js_rules` (4 + 6 файла) | 1.91 s / 3.45 s | 0.84 s / 2.45 s |
| `load_styles()` обединен (4 извиквания) | 20.09 s | **7.41 s** |
| Повторни извиквания (3) | — | 0.002 s |
| Обединен резултат | — | байт-идентичен, SHA-256 `8fc6ec…ae66` |

Сигурностният договор е запазен без промяна: отказ на символна връзка **преди**
разрешаване, проверка на границата след `realpath`, суфикс `.js`, проверки за
съществуване и `isFile()`, таван 200 000 знака, VM без `strings`/`wasm` и
1000 ms таймаут.

### 8.2 Нов ред в тестовия план

| # | Сценарий |
| --- | --- |
| T31 | Панелът и индикаторът в главния панел следват избрания език (en/bg/de) |
| T32 | Динамичните редове запазват данните си (име на файл, брой) на всеки език |
| T33 | Правилата за JS стилове се зареждат с един Node процес и дават байт-идентичен резултат; кешът на стиловете се инвалидира явно (T33 = 21 теста в `tests/test_v90_js_rule_loader.py`) |
