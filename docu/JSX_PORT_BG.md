# JS портове на Python helper-ите (`tools/jsx/`)

Документът описва втората половина на задачата „прецизни функции, изцяло изградени с JS“: 1:1 портове на
Python helper-ите на проекта, доказани срещу **реалните** Python функции, а не срещу ръчно написани
очаквания.

## 1. Метод на доказване (parity fixtures)

Ръчно написано очакване проверява само това, което авторът вече знае. Затова всеки порт се доказва по
схемата:

1. `tools/jsx/parity/make_reference.py` (и `make_style_reference.py`) внасят **оригиналните Python модули**
   и записват резултатите им в JSON: `tools/jsx/test/fixtures/parity.json` и `styles.json`.
2. JS тестовете четат същия JSON и сравняват изхода на порта с записания Python изход.
3. Регенерация: `npm run reference:jsx`.

Така fixture-ът е свидетелство за поведението на Python, включително за грешките и съобщенията им. Ако
Python функцията се промени, fixture-ът се регенерира и тестът показва разликата.

## 2. Инвентар на портовете

| JS модул | Python оригинал | Съдържание |
| --- | --- | --- |
| `lib/glob.mjs` | `fnmatch` (stdlib) | `translate`, `fnmatchcase`, `fnmatch` с Windows-съвместима семантика |
| `file-filters.mjs` | филтрите на GUI-то | `ENV_FILTERS`, `MAX_FILTER_LENGTH` (512), `normalize`, `parse`, `caseSensitive`, `matches`, `describe`, `fromEnv`, `toEnv`, `auditPayload` |
| `hash-table.mjs` | таблицата с хешове | форматиране и подредба на редовете, обвиване на дълги стойности |
| `style-loader.mjs` | `style_loader.py` + `js_rules.py` + `js_rules_runner.cjs` + `style_runtime.py` | зареждане и сливане на 32-те `*.js` правила в процеса, без подпроцес |
| `presentation-policy.mjs` | `document_presentation_policy.py` | `pyInt`, `formatFileSize`, `formatDigest`, `normalizeText`, `assertTableFragment` |
| `report-profile.mjs` | `chronoseal/unified_report_profile.py` | `PROFILE_FIELDS`, `DEFAULT_PROFILE`, `auditOptions`, `toDict`, `assertProfile` |
| `pagination-policy.mjs` | `pagination_policy.py` | `paginationConfig`, `keepShortSection`, `keepHeadingWithFirstParagraph` |

Всеки модул изнася и snake_case псевдоними (`load_styles`, `format_file_size`, …), за да може портът да се
използва като директна замяна в код, който още вика Python имената.

## 3. `style-loader.mjs` — най-важният порт

Python вариантът пуска `js_rules_runner.cjs` като **подпроцес** за всяка папка с правила. Портът прави
същото in-process с `node:vm`, като запазва всички защити на оригиналния runner:

* `lstat` проверка и отказ на символни връзки (`SYMLINK`);
* `realpath` граница — файл извън папката се отказва (`OUTSIDE`);
* задължителна `.js` приставка (`SUFFIX`);
* таван 200 000 B на файл (`TOO_LARGE`);
* VM контекст със `strings: false` и `wasm: false` и 1 s таймаут (`EVALUATION`);
* коренът на правилото трябва да е обект, не масив (`NOT_OBJECT`).

Сливането е рекурсивно; дублиран ключ в два файла е грешка, а не „последният печели“. Задължителните 16
секции се проверяват само за пакетираната папка с правила — същото поведение като Python.

Резултатът е **побайтово идентичен** с Python: 52 секции, 28 674 B JSON, `equal: True`. Кешът връща
дълбоко копие при всяко извикване; `invalidate()` принуждава истинско повторно четене.

Намерен дефект в Python: при `EVALUATION` и `NOT_OBJECT` съобщението на `js_rules.py` съдържа суровия repr
на подпроцеса — `Command '['C:\\Program Files\\nodejs\\node.EXE', …]' returned non-zero exit status 2.` —
който изтича пътя до Node, пълния аргументен вектор и вътрешния JSON на runner-а. Портът връща само
смислената част от съобщението, а fixture-ът изрично отбелязва `leaks_subprocess_repr: true`, за да е
видимо, че разликата е поправка, а не разминаване.

## 4. Съзнателни разлики

| Python | JS порт | Причина |
| --- | --- | --- |
| `keep_short_section` връща `KeepTogether` | връща `{strategy: 'keep', gapPt}` | портът няма ReportLab; политиката е отделена от рендирането |
| `str(None)` → `"None"` | същото | запазено за побайтово равенство |
| частичен dataclass е невъзможен | `assertProfile` хвърля `TypeError` | Python не може да конструира непълен профил, затова няма референтно поведение |
| `layout_rule` ходи само в `CENTRAL_LAYOUT` | същото + `PAGINATION` е достъпен само през корена | документирано в `styles.json` като `out_of_scope` / `merged_root` |

## 5. Тестове

| Файл | Брой | Покритие |
| --- | --- | --- |
| `test/file-filters.test.mjs` | 11 | разбор, нормализация, съвпадение, env обмен |
| `test/hash-table.test.mjs` | 10 | подредба, форматиране, дълги стойности |
| `test/style-loader.test.mjs` | 17 | payload, задължителни секции, visual/layout, всички error кодове, кеш, invalidate, обхождане |
| `test/policy.test.mjs` | 13 | presentation, profile, pagination |

Общо с `tools/pdfnorm/test/`: **75 теста, 75 успешни, 0 неуспешни** (`npm run test:js`).

## 6. Оставащи helper-и

Още не са портнати: `chronoseal/util.py` (`sha256`, `atomic_json`), `page_identity.py`, `pipeline.py`,
`i18n.py`, `pdf_object_rules.py`, `report_header.py`, `safe_table.py`, `module_loader.py`,
`evidence_database.py`, `branding.py`, `trusted_lists.py`, `report_quality.py`, `storage_identity.py`,
`settings.py`, `progress_heartbeat.py`. Редът е по зависимост: първо `util.py`, после останалите.