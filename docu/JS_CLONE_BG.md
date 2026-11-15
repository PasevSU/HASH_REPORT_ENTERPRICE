# HASH REPORT — клонинг на чист JavaScript (`js/`)

Документът описва `js/` — самостоятелен клонинг на генератора на HASH REPORT, изграден **само с Node.js
и вградените му модули**. Клонингът възпроизвежда пълната верига на Python генератора: избор на файлове →
хеш таблица → PDF отчет → PDF/A-2b нормализация → доказателствен пакет → неизменяем архив със SQLite.
Той не съдържа GUI и не подписва с RFC3161.

## 1. Защо

Python генераторът изисква интерпретатор, `pytz`, `reportlab`/`fpdf`, `pikepdf`, `PyMuPDF` и `fontTools`.
Клонингът трябва да произведе **същия отчет и същия доказателствен пакет без нито една външна
зависимост**, така че да работи на машина, на която е наличен само Node.js ≥ 22.12 (вградени `node:sqlite`,
`node:crypto`, `node:zlib`).

Клонингът **не променя** съществуващото състояние на проекта: Python модулите, GUI-то, автоматизацията и
конфигурацията остават непокътнати. Споделени са само вече съществуващите JS портове: `tools/jsx/`
(граматика на филтрите и правилата за стил) и `tools/pdfnorm/` (PDF парсер, writer, subsetting).

## 2. Структура

| Файл | Роля |
| --- | --- |
| `cli.mjs` | Входна точка: `parseArgs`, шестте етапа на `run()`, обобщение, изходни кодове |
| `api.mjs` | Програмен API: `buildArgv`, `prepareOutput`, `reportForFolder`, `reportForFile`, `reportForFiles` |
| `HashReport.bat` | Меню-стартер за Windows: събира опциите и извиква `node js/cli.mjs` |
| `lib/config.mjs` | Чете `config.json`; `generatorSettings`, `evidencePolicy`, `archiveSettings`, `toolPath` |
| `lib/selection.mjs` | `resolveSelection` / `discover` — рекурсия, филтри, `MAX_FILES = 20000`, относителни пътища |
| `lib/util.mjs` | `sha256File`, `sha256Bytes`, `atomicWriteBytes/Json`, `jsonSafe`, `formatUtc`, `posix`, `A4_PT` |
| `lib/identity.mjs` | `reportId`, `documentName`, `isGeneratedHashReport`, системна/потребителска/томна информация; разпознава всичките шест маркера `_HASHREPORT_TYP_*` |
| `lib/generate.mjs` | Оркестрация на отчета: `hashSelection`, `aggregatePayload`, `aggregateProof`, `describeFile`, триминаващ рендер и цикъл на сходимост |
| `lib/classify.mjs` | `classifyArtifactFile` — точно копие на Python `_classify_artifact_file`, `TYPE_PRIORITY`, `typeCounts` |
| `lib/report.mjs` | Съдържание и оформление: типове редове, колони, формати на клетките, единадесетте дийджеста; `REPORT_TYPE_LABELS`, `reportType()` |
| `lib/embed.mjs` | `describeSourcePdf`, `appendSourcePages`, `attachOriginal` — вграденият изходен PDF за типа `single_pdf` |
| `lib/reports/index.mjs` | Регистър на шестте типа: `REPORT_MODULES`, `loadReportModule`, `reportModuleIds`, `listReportModules`, `renderReportSections` |
| `lib/reports/sections.mjs` | Шестте споделени секции: `timestamp_record`, `generation_note`, `legal_documentation`, `text_checksums`, `source_pdf_evidence`, `volume_breakdown`; `getSection` хвърля при непознат идентификатор |
| `lib/reports/checksums.mjs` | Двигател на текстовите хешове: `PAGE_TEXT_ALGORITHMS` (6), `ALL_TEXT_ALGORITHMS` (11), `digestText`, `digestBytes`, `digestLength`, `normalisePageText`, `framePageTexts`, `pageDigests`, `documentDigests`, `footerHashLines`, `placeholderDigests` |
| `lib/reports/{single,single_pdf,combo,combo_all,volume,file_information_report}.mjs` | По един самостоятелен модул за всеки тип — секциите и редът им като в съответния Python профил |
| `lib/pdf/builder.mjs` | Авторски PDF слой върху `tools/pdfnorm/lib/parser.mjs` (шрифтове, subsetting, `/ToUnicode`) |
| `lib/pdf/layout.mjs` | Абсолютно позициониране, колони, пренос на редове, футър с `totalPages` |
| `lib/fonts.mjs` | Избор на системни TrueType шрифтове (Arial / Times New Roman) |
| `lib/normalize.mjs` | `normalizeReport` — PDF/A-2b чрез `tools/pdfnorm/normalize.mjs`, `inspectPdf` за прочит обратно |
| `lib/quality.mjs` | `auditLayout` — гейт PASS/REVIEW преди публикуване |
| `lib/evidence.mjs` | `inspectStorage`, `inspectWorkspaces`, `lowSpaceWarning`, `caseDirectory`, `writeEvidence` |
| `lib/archive.mjs` | `archiveReport` (неизменяема папка + SQLite), `readArchivedFile`, `renameWithRetry` |
| `test/core.test.mjs` | 7 unit теста: филтри, откриване, агрегация, класификация, идентичност, формати, политика |
| `test/workflow.test.mjs` | 8 интеграционни теста: пълен отчет, филтриран + SINGLE, невалидни аргументи, архив, самоизключване, per-file |
| `test/api.test.mjs` | 7 теста на програмния API: преобразуване на опциите, създаване на папка, SINGLE/COMBO, изолация на грешка, валидация |
| `test/embed.test.mjs` | 7 теста на вградения изходен PDF: геометрия и прикачен оригинал, отказ за не-PDF, отказ при повече от един файл, отказ за чужд профил, отказ на типа `single_pdf` без вграждане, пълен `single_pdf` отчет, per-file с вграждане |
| `test/reports.test.mjs` | 9 теста на шестте типа: по един модул на профил без сираци, всички секции се резолвват, редът на секциите, хешовете във футъра се преизчисляват от нарисувания текст, обхватът на документа, приложението не хешира себе си, съдържание на двата специални типа, шестте маркера, изключване на хешовете |

## 3. CLI

```
node js/cli.mjs --source <folder> [--recursive] [--filter PATTERN]...
node js/cli.mjs --files <file[,file...]> [--output <folder>]
```

| Опция | Значение |
| --- | --- |
| `--source <folder\|file>` | Папка за отчет, или един файл за SINGLE отчет |
| `--recursive` | Включва подпапките (маркира COMBO отчета с `_ALL`) |
| `--filter <pattern>` | Повтарящ се филтър, същата граматика като GUI (`*.pdf`, `*eml.pdf`) |
| `--files <list>` | Явен избор, разделен със запетая или нов ред; филтрите не важат |
| `--output <folder>` | Къде се публикува готовият отчет (по подразбиране: папката-източник) |
| `--profile <id>` | Профил от `hash_report_generator/report_profiles` — `single`, `single_pdf`, `combo`, `combo_all`, `volume`, `file_information_report` (по подразбиране `single` за един файл, иначе `combo`) |
| `--per-file` | По един самостоятелен SINGLE отчет за всеки избран файл — собствен номер, доказателствена папка и архивен ред |
| `--embed-pdf` | Само за един PDF вход и само за профил `single` / `single_pdf`: страниците на изходния PDF се добавят след отчета, а оригиналът се прикачва байт по байт (паритет с `single_pdf`). Без него `--profile single_pdf` се отказва, защото името би описало съдържание, което документът не носи |
| `--archive` / `--no-archive` | Принудително включва/изключва архива независимо от конфигурацията |
| `--no-normalise` | Оставя PDF-а без PDF/A-2b етапа |
| `--require-layout-pass` | Блокира публикуването при `REVIEW` от layout гейта |
| `--json` | Машинно четимo обобщение на stdout |
| `--quiet` | Само предупреждения и грешки |

Изходни кодове: `0` (`PASS`), `1` (`ERROR`), `2` (`BLOCKED` — layout `REVIEW` при `--require-layout-pass`).

Явният избор (--files) при един файл винаги дава профил single, дори когато --source сочи папка:
папката само фиксира относителните пътища, а отчетът остава _HASHREPORT_TYP_SINGLE.pdf.

Чрез `package.json`: `npm run clone -- --source <folder>` и `npm run test:clone`.

## 4. Шестте етапа

1. **Избор.** `resolveSelection` прилага филтрите, рекурсията и явния списък; генерираните отчети се
   изключват от доказателствения набор (`isGeneratedHashReport`) и броят им се записва в манифеста.
2. **Хеширане.** Всеки файл се описва с `sha256`, размер и тип; счита се `aggregate_proof =
   sha256(concat(sha256_hex_lower + relative_name))`.
3. **Отчет.** Триминаващ рендер (виж раздел 4.1). Името е
   `{report_id}_HASHREPORT_TYP_{SINGLE|SINGLE_PDF|COMBO|COMBO_ALL|VOLUME|FILE_INFORMATION}.pdf`.
4. **PDF/A-2b.** `normalizeReport` вгражда подмножества на шрифтовете, добавя sRGB output intent, XMP с
   `pdfaid:part=2`/`pdfaid:conformance=B` и поправя xref; `inspectPdf` прочита обратно страници,
   метаданни и output intent.
5. **Доказателства.** `ChronoSeal_Evidence/<stamp>/` с `storage-identity.json`, `layout-audit.json`,
   `manifest.json` (схема 1) и `run.log`.
6. **Архив.** `archiveReport` копира отчета и доказателствата в неизменяема папка, записва редовете в
   SQLite (`node:sqlite`) и отказва повторен `report_id` (`refusing overwrite`).

### 4.1 Шестте типа отчети

Всеки тип живее в собствен модул под `lib/reports/` и описва само своя ред на секции; съдържанието на
секциите е общо, за да не се разминават типовете едно от друго.

| Профил | Маркер в името | Секции по ред |
| --- | --- | --- |
| `single` | `_TYP_SINGLE` | `timestamp_record`, `generation_note`, `legal_documentation`, `text_checksums` |
| `single_pdf` | `_TYP_SINGLE_PDF` | `timestamp_record`, `source_pdf_evidence`, `generation_note`, `legal_documentation`, `text_checksums` |
| `combo` | `_TYP_COMBO` | `timestamp_record`, `generation_note`, `legal_documentation`, `text_checksums` |
| `combo_all` (рекурсивен `combo`) | `_TYP_COMBO_ALL` | `timestamp_record`, `volume_breakdown`, `generation_note`, `legal_documentation`, `text_checksums` |
| `volume` | `_TYP_VOLUME` | `volume_breakdown`, `generation_note`, `legal_documentation`, `text_checksums` |
| `file_information_report` | `_TYP_FILE_INFORMATION` | `timestamp_record`, `generation_note`, `text_checksums` (без правния препечат) |

Маркерът е и самоличност: `isGeneratedHashReport` разпознава точно тези шест имена, затова отчет,
публикуван от клонинга, никога не влиза в доказателствения набор на следващ отчет.

### 4.2 Триминаващ рендер и текстови хешове

Отчетът съдържа хешове на собствения си текст, затова не може да се нарисува наведнъж. `runPass()`
минава три пъти:

1. **Репетиция.** `context.checksums` е запълнен с `placeholderDigests` (букви `X` с точната дължина на
   всеки дийджест), така че пренасянето на редове и броят страници съвпадат с готовия документ байт по
   байт.
2. **Истински дийджести.** `documentDigests(rehearsal.bodyTexts)` дава единадесетте дийджеста за целия
   документ, а `pageDigests(text)` — по един запис на страница. Обхватът (`scope.pageCount`) се
   снима **преди** изчертаването на секциите на типа, за да не хешира приложението само себе си.
3. **Хешове във футъра.** `footerHashLines(pageDigests(...))` се подава на `ReportLayout` през
   `footerHashes`; ако броят страници се промени, стъпката се повтаря веднъж.

`ReportLayout` прихваща `builder.drawText` в конструктора и записва всеки низ с `band !== 'footer'` в
`pageTexts`. Така съдържанието на футъра никога не влиза в собствения си хеш, а публикуваните стойности
могат да се преизчислят от нарисувания документ — точно това проверява `test/reports.test.mjs`.

Около рендера работи цикъл на сходимост: при `single_pdf` вградените страници добавят височина, което
може да смени броя страници, затова `runPass()` се повтаря до 3 пъти, докато
`context.embeddedPdf.reportPages === pass.pageCount`.

`generateReport({ textChecksums: false })` изключва стъпка 2 и 3 и връща `textChecksums: null` — тогава
отчетът е лек, но не носи доказателство за собствения си текст. Това е вътрешна опция на генератора;
CLI и `js/api.mjs` нарочно не я подават, защото публикуваният отчет винаги трябва да носи хешовете си.

## 5. Съответствие с Python

| Аспект | Python | Клонинг |
| --- | --- | --- |
| Име на отчета | `{id}_HASHREPORT_TYP_{COMBO,COMBO_ALL,SINGLE,SINGLE_PDF,VOLUME,FILE_INFORMATION}.pdf` | същото, включително `_ALL` |
| Самоизключване | `_is_generated_hash_report` (регекс за всички шест маркера) | `isGeneratedHashReport` (същият набор) |
| Текстови хешове | MD5/SHA-1/224/256/384/512/SHA3-224/256/384/512/RIPEMD-160 на текста на всяка страница, плюс блок във футъра | същото, `lib/reports/checksums.mjs` |
| `report_id` | `RPT-YYYYMMDD-HHMMSSmmm-XXXXXXXX` | същото |
| Хеш | `sha256` на файла, lowercase hex | същото |
| `aggregate_proof` | `sha256(join(sha256_hex + относително_име))` | същото (проверено независимо с `hashlib`) |
| Класификация | `_classify_artifact_file` (`.eml`, `.sig`, `.sha256`, `.pdf`, само `.txt`, `.html`, `.bin`, `.json`, `attachments*`) | същото, включително `beta.log`/`gamma.csv` → `OTHER` |
| Формат на размера | `int(bytes)/1024.0` с 3 знака | същото |
| Дийджест колона | `group = int(width/(size*0.62))`, clamp 8..32, `-= group % 4` | същото |
| Единадесет дийджеста | `Total Checksum (All Files)`: MD5, SHA-1/224/256/384/512, SHA3-224/256/384/512, RIPEMD-160 | същото |
| Финал | PDF/A-2b | същото |

**Умишлени различия (документирани, не са дефекти):**

- **Без RFC3161.** Клонингът никога не подписва и не твърди подпис; манифестът описва точно какво е
  произведено. Затова `evidencePolicy` изисква `keep_tsr`, `keep_certificates`, `keep_validation_json`
  да са включени — те са запазени за пълен паритет на схемата, но не се създават TSR файлове.
- **Часова зона.** Python фиксира `pytz.timezone('Europe/Berlin')` и печата `CET/CEST`. Node чете
  системната зона, затова `timezoneText()` печата `<кратко име> <±HH:MM>`; при зона, която дава само
  отместване (`GMT+2`), се печата само `+02:00`, за да няма излишен префикс.
- **`_ALL` при рекурсия.** `documentName({recursive:true})` добавя `_ALL` към `COMBO`. И двата
  реализирани регекса за самоизключване (`isGeneratedHashReport` в JS и `_is_generated_hash_report` в
  Python) вече покриват `_TYP_COMBO_ALL`, така че рекурсивен отчет не се брои за доказателство и в
  двете приложения. `documentName` приема базовия тип и сам слага `_ALL`; подаване на `COMBO_ALL` като
  `kind` се отказва с `Unsupported report kind`.
- **`pageLabels: false`.** `tools/pdfnorm/normalize.mjs` по подразбиране добавя BSI схемата за етикети
  (валидна за `esig_pdf.pdf`); клонингът я изключва, за да не получава отчетът чужди етикети `i..vii`.
  Опцията е описана в `docu/PDFNORM_JS_BG.md`.

## 6. Тестове

`node --test js/test/` (или `npm run test:clone`).

| Тест | Какво доказва |
| --- | --- |
| `the filter grammar takes the GUI patterns and dedupes them` | `parse`/`describe`/`matches` от `tools/jsx/file-filters.mjs`, дедупликация без значение на регистъра, `none` |
| `discovery honours filters and recursion, and report detection is separate` | филтри, подпапки, генерираните отчети се броят отделно от избора |
| `the aggregation proof matches an independent Python computation` | `aggregate_proof` срещу независимо изчисление с `hashlib` |
| `artifact classification follows the Python branch order` | 12 имена по клоните на `_classify_artifact_file` |
| `report identity keeps the _ALL marker a suffix and stays detectable` | `reportId`, `documentName`, `isGeneratedHashReport` за 4 модерни и 3 не-отчета |
| `cell formatters mirror the reference layout` | `sizeKb`, `digestGroup` (кратно на 4), двуредов `timestampCell`, `timezoneText`, `localStamp` |
| `evidence retention flags cannot be switched off` | трите задължителни ключа, отказ на `keep_tsr:false`, отказ на не-обект |
| `a folder run publishes a PDF/A-2b report with evidence` | `PASS`, `{part:'2',conformance:'B'}`, `_HASHREPORT_TYP_COMBO.pdf`, `%PDF-`, четири доказателствени файла, кръстосани проверки в манифеста |
| `filters narrow a folder run and an explicit selection makes a SINGLE report` | `files === 1` при филтър; `_HASHREPORT_TYP_SINGLE.pdf` при `--files` |
| `invalid argument combinations are refused before any file is written` | липсващ `--source`, филтър с `--files`, `--recursive` върху файл, липсващ източник, филтър без стойност |
| `the archive publishes once and then refuses a duplicate report id` | публикуване, четири артефакта, четене обратно на `evidence/manifest.json` от SQLite, отказ с `refusing overwrite` |
| `a second recursive run never hashes the report it produced first` | `selection_excluded_reports >= 1`, `selection_count === files` |

| `per-file mode publishes one SINGLE report per selected file` | 3 файла → 3 отчета, различни `report_id`, `pdf_sha256` и доказателствени папки, всички `_HASHREPORT_TYP_SINGLE.pdf` |
| `per-file mode honours an explicit file list` | `--files` + `--per-file` → два SINGLE отчета с различни номера |
| `per-file mode refuses a forced report profile` | `--per-file --profile combo` се отказва преди писане |
| `buildArgv maps every option onto the CLI grammar` | всички опции на API-то се превръщат в точния аргументен вектор |
| `prepareOutput creates a nested output folder the CLI would refuse` | вложена папка се създава, повторното извикване е безвредно |
| `reportForFile publishes one SINGLE report` | SINGLE име, `manifest.json` в доказателствената папка |
| `reportForFolder publishes one COMBO report` | COMBO име и брой файлове |
| `reportForFiles keeps the good reports when one file cannot be read` | липсващ файл → `failed 1`, `status ERROR`, двата четими файла са публикувани; при `continueOnError: false` грешката се хвърля |
| `the API validates its inputs instead of publishing an empty report` | липсващ файл/папка, файл вместо папка, папка вместо файл, празен списък |

Резултат: **38/38 клонинг** (7 core + 8 workflow + 7 API + 7 embedded PDF + 9 типа, ~30 s), **75/75**
съществуващи JS тестове (`tools/pdfnorm/test/`, `tools/jsx/test/`), **122/122** Python теста в
модулите, засегнати от разширеното самоизключване (`tests/test_hardening.py`,
`tests/test_file_selection.py`, `tests/test_ui_selection_filters.py`, `tests/test_report_archive.py`,
`hash_report_generator/tests/test_migration_contracts.py`) — всички минават.

Проверка на самите типове извън тестовете: `single`, `combo`, `combo_all`, `volume` и
`file_information_report` бяха пуснати през CLI върху реална папка и публикуваха съответно
`_TYP_SINGLE`, `_TYP_COMBO_ALL`, `_TYP_COMBO_ALL`, `_TYP_VOLUME`, `_TYP_FILE_INFORMATION` — нито един
тип не се представя за друг.

### Измерен резултат

| Показател | Стойност |
| --- | --- |
| Входни файлове | 2 |
| Страници | 2 |
| PDF | 97 254 байта, PDF/A-2b |
| Layout гейт | PASS |
| Време | 3.4 s |

## 7. Програмен API (`js/api.mjs`)

Модулът връща същите обобщения, които CLI отпечатва, така че извикващият код никога не трябва да
разчита конзолен текст.

| Функция | Връща |
| --- | --- |
| `buildArgv(options)` | масив от аргументи за `run()`; без странични ефекти |
| `prepareOutput(directory)` | създава папката с `recursive: true` и връща абсолютния път (CLI отказва несъществуваща папка) |
| `reportForFolder(folder, options)` | `{exitCode, summary, layout, published, evidenceDirectory, archive}` за COMBO отчет |
| `reportForFile(file, options)` | същото, но за един файл (SINGLE) |
| `reportForFiles(files, options)` | `{exitCode, status, files, failed, reports[], elapsed_seconds}` — по един отчет на файл |

Опции: `source`, `files`, `filters`, `recursive`, `output`, `profile`, `archive` (`true` / `false` /
`null` = по конфигурация), `normalise`, `requireLayoutPass`, `perFile`, `quiet`, `log`,
`continueOnError`, `repoRoot`. `log: true` връща конзолния изход на CLI, иначе API-то мълчи.

```js
import { reportForFiles } from './js/api.mjs';

const batch = await reportForFiles(['D:/case/a.eml', 'D:/case/b.pdf'], {
  output: 'D:/reports',
  archive: true,
});
console.log(batch.status, batch.failed, batch.reports.map((r) => r.summary.report_id));
```

`continueOnError` е `true` по подразбиране: нечетимият файл увеличава `failed`, но отчетите на
останалите файлове се публикуват и `status` става `ERROR`. При `continueOnError: false` първата
грешка се хвърля веднага.

## 8. Стартиране с `.bat` файл (`js/HashReport.bat`)

Файлът е меню, което само събира опции и след това извиква `node js/cli.mjs`, така че резултатът е
винаги идентичен с командната линия. Стартира се с двойно щракване или с `npm run clone:gui` от
монтирано устройство.

| Точка | Действие |
| --- | --- |
| 1 | Папка или един файл (влачене и пускане върху конзолата работи) |
| 2 | Рекурсия — включва подпапките |
| 3 | Филтри: добавят се един след друг, докато не се въведе празен ред |
| 4 | Изчиства всички филтри |
| 5 | Изходна папка; създава се, ако липсва |
| 6 | Режим „по един отчет на файл“ (`--per-file`) |
| 7 | Архив: `config` (по конфигурация), `on`, `off` |
| 8 | Строг layout гейт (`--require-layout-pass`) |
| 9 | Явен списък файлове, по един път на ред |
| 10 | Вграден изходен PDF (`--embed-pdf`): отчетът и оригиналът в един файл, само за един PDF вход |
| 11 | Тип отчет (`--profile`): `auto` → `single` → `combo` → `combo_all` → `volume` → `file_information_report` → `single_pdf` → `auto` |
| R / H / Q | Стартиране / помощ / изход |

Преди стартиране менюто отпечатва точната команда, за да може същата линия да се използва в скрипт.
След приключване се показват изходният код и един от трите резултата: `PASS` (0), `LAYOUT REVIEW` (2)
или `ERROR` (1).

Технически бележки:

- `pushd "%~dp0.."` се използва вместо `cd`, защото `cmd.exe` не приема UNC работна директория;
  `pushd` временно монтира устройство и така стартерът работи и от мрежов дял.
- Затварящата скоба в `echo` се екранира, а резултатът се отпечатва от подпрограма `:RESULT`, за да
  не се скъса блокът `if`.
- Кавичките от път, получен чрез влачене, се премахват, а изходната папка се създава предварително.
- `--profile` се добавя към командата само когато `%PROFILE%` не е `auto` и не е включен per-file режим
  (per-file винаги публикува `SINGLE` отчети). Така `auto` остава поведението на CLI по подразбиране.
- Точка 11 само превключва стойността — менюто не проверява комбинации; несъвместима комбинация (например
  `--embed-pdf` с `--profile combo`) се отказва от CLI преди да е записан файл, с ясно съобщение.

## 9. Ограничения

- Няма графичен интерфейс на графична библиотека и няма подписване — стартерът `js/HashReport.bat` е
  само меню върху CLI, а подписването остава отделен модул на Python приложението.
- `npm run` не работи, когато работната директория е UNC път (`cmd.exe` не приема UNC); извиквайте
  `node js/cli.mjs` и `node --test js/test/` директно или работете от монтирано устройство.
- Клонингът пише само в `--output` и в `%TEMP%` по време на тестовете; в репозиторито не се създават
  `*.sqlite3`, `*.db` или `RPT-*.pdf` (изискване на `.github/workflows/repo-guard.yml`).
- `--embed-pdf` (тип `single_pdf`) работи само с **един** PDF вход и само с профил `single`; всичко друго
  се отказва с грешка преди писане. Отчетът расте с размера на изходния файл, защото оригиналът се
  прикачва байт по байт — неподходящо за много големи източници.
- Хешовете на текста доказват **съдържанието на страниците**, а не авторство или време. Те не заменят
  TSA маркер; затова редовете за времеви печат остават `NOT APPLIED` / `NOT VERIFIED` / `NOT SEALED`.