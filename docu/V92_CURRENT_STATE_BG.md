# V92 — Актуално състояние и работа на ChronoSeal Enterprise

Документът описва **какво прави програмата днес** в това издание: версия
`5.10.0-cli`, без графичен интерфейс, с оркестратор на отчетите по име и с `--url`,
който задава хоста на проверката. Подробно за изданието — `V95_CLI_EDITION_BG.md`.

Двете издания произлизат от `main` (`5.10.0`): `release/gui` е графичното издание
без QR код (за бързи действия и изпращане по имейл), а `release/cli` е това —
само команден ред, със задължителен QR блок във всеки отчет.

## 1. Два независими номера на версия

| Номер | Къде живее | Какво означава |
|---|---|---|
| `5.10.0-cli` | `chronoseal/branding.py` (`VERSION`), `package.json`, таблицата в `README.md` | Версия на Python пакета в CLI изданието |
| `CLONE_VERSION` | `js/cli.mjs` (`CLONE_VERSION = '1.0.0'`), вгражда се в `manifest.implementation` | Версия на независимия JavaScript клонинг |

Двете версии се движат отделно: JS клонингът се разпространява като отделен продукт
(`js/HashReport.bat`, `js/api.mjs`) и не изисква Python.

## 2. Точки на влизане

| Вход | Файл | Предназначение |
|---|---|---|
| Оркестратор по име на отчет | `chronoseal_report.py` (`Run_Report.bat`) | `SINGLE`, `SINGLE_PDF`, `COMBO`, `COMBO_PDF`, `COMBO_ALL`, `COMBO_ALL_PDF`; `list`, `--information`, `--version` |
| Команден ред (Python) | `chronoseal_cli.py` | `--profile`, `--source`, `--output`, `--embed-pdf`, `--embed-position`, `--source-pdf`, `--explanation`, `--qr-url`, `--url`, `--filter`, `--file`, `--json`, `--preflight`, `--self-check`, `--bootstrap-trust` |
| Неподпечатан диагностичен runtime | `chronoseal_process_cli.py` + `automation/*.bat` | Само UNSEALED JSON доказателства; изисква `--allow-unsealed-diagnostics` |
| Обвивки за вграждане | `automation/COMBO_PDF.bat`, `automation/COMBO_ALL_PDF.bat` | Подпечатан път (`chronoseal_cli.py`); приемат `INPUT OUTPUT EMBED_PDF [before|after]` |
| Обвивки без вграждане | `automation/SINGLE.bat`, `SINGLE_PDF.bat`, `COMBO.bat`, `COMBO_ALL.bat` | Само неподпечатан диагностичен runtime (`chronoseal_process_cli.py`) |
| JS клонинг (CLI) | `js/cli.mjs` (`node js/cli.mjs`) | Пълен отчет без Python и без RFC3161 |
| JS клонинг (меню) | `js/HashReport.bat` | Стартира същия клонинг с меню за избор |

Графичните входове (`ChronoSeal_GUI.pyw`, `ChronoSeal_Original_Legacy.py`,
`ChronoSeal_OneButton.py`, `Start_ChronoSeal.bat`, `automation/Start_Automation.py`,
`automation/Unified_ChronoSeal.py`, `automation/*_Panel.py`, `ui/`) **не съществуват**
в този клон — те са в `release/gui`. `Install_Windows.bat` не стартира нищо, а
отпечатва имената на отчетите и пример за употреба.

## 3. Типове отчети

Маркерът в името е договор: по името се познава какво съдържа файлът, без да се отваря.

| Тип | Профил | Обхват | Вграден PDF |
|---|---|---|---|
| `SINGLE` | `single` | един файл | не |
| `SINGLE_PDF` | `single_pdf` | един PDF файл | **да** — самият входен файл |
| `COMBO` | `combo` | папка (без подпапки) | не |
| `COMBO_ALL` | `combo_all` | папка с подпапки | не |
| `COMBO_PDF` | `combo_pdf` | папка (без подпапки) | **да** — един избран PDF |
| `COMBO_ALL_PDF` | `combo_all_pdf` | папка с подпапки | **да** — един избран PDF |
| `VOLUME` | `volume` | том/дял | не |
| `FILE_INFORMATION` | `file_information_report` | един файл, без правен препис | не |

Правило за име:

```
RPT-YYYYMMDD-HHMMSSmmm-XXXXXXXX_HASHREPORT_TYP_<ТИП>.pdf
```

`_ALL` се вмъква **преди** `_PDF`, затова рекурсивен отчет с вграден PDF се казва
`..._TYP_COMBO_ALL_PDF.pdf`, а не `COMBO_PDF_ALL`. Генераторът винаги произвежда
`_SINGLE` или `_COMBO`; суфиксите `_ALL` и `_PDF` се добавят при публикуване
(`chronoseal/pipeline.py`, блокът за име на изхода), така че вътрешно генерираният
файл никога не носи име, което публикацията после би объркала.

## 4. Конвейер на Python изданието

`Pipeline.run()` минава през шест стъпки, всяка от които се логва:

0. **Preflight** — проверка на входа, режима, инструментите, `input_kind`
   (`source` / `pdf_embed` / `combo_embed`).
1. **Generate report** — `hash_report_generator` се стартира като отделен процес
   (само през environment променливи, без внос на ChronoSeal), произвежда
   `..._TYP_SINGLE.pdf` или `..._TYP_COMBO.pdf` в частна работна папка.
2. **Сглобяване** — `_compose()`: страниците на отчета, по избор ERLAEUTERUNG,
   по избор вграден PDF (преди или след отчета), после футър/идентичност на
   страниците (`page_identity.apply_footer`).
3. **RFC3161** — независим START и STOP DocTimeStamp, DSS/Certs, повторна проверка.
4. **Final verification** — файлът се отваря наново; проверяват се точно две
   ChronoSeal ревизии.
5. **Evidence** — `manifest.json` и придружаващите JSON файлове в case папка.
6. **Публикуване** — едва след PASS файлът получава окончателното си име.

Всичко междинно живее в `ChronoSeal_Evidence/<RUN>`; публикуваният PDF никога не
съществува като UNSEALED файл под окончателното си име.

### Артефакти в case папката

| Файл | Съдържание |
|---|---|
| `manifest.json` | Пълен запис: избор, хешове, `embed_position`, `rfc3161_audit`, статус |
| `embedded-original.json` | `filename`, `sha256`, `size`, `verification`, `visible_pages`, `first_visible_page`, `embed_position`, `text_identity_appendix_pages`, `signature_audit`, `source_signature_status` |
| `source-pdf-signature-audit.json` | Инвентар на подписите в източника (не ги валидира) |
| `page-identity.json` | Секции, `placement`, `geometry_policy: preserve_original`, `page_count` |
| `storage-identity.json` | Идентичност на носителя/пътя |
| `layout-audit.json` | Резултат от проверката на оформлението |
| `verification-qr.json` | Адресът на задължителния QR блок и дали изображението е нарисувано |
| `logs/` | Пълният лог на сесията |
| `hash_report_evidence.sqlite3` | Машиночитаемо доказателство |

## 5. Договор за вградения PDF

Трите гаранции (еднакви в Python и в JS клонинга):

1. **Геометрия** — внесените страници запазват оригиналния си размер; нищо не се
   преоразмерява и не се пре-кодира.
2. **Байтова идентичност** — оригиналът пътува като `/EmbeddedFiles` прикачен файл и
   е байт-за-байт равен на изходния файл (`checks.attachment_sha256`).
3. **Проверка след сериализация** — и двете се проверяват след запис и се записват в
   `source-pdf-signature-audit.json`.

Допълнително:

* Внесената страница получава футър в **допълнителна долна лента** (`collision_boundary_from_bottom_pt`,
  ≈ 91 pt), така че нито един оригинален глиф да не бъде закрит.
* Винаги се добавя една страница с текстов контролен списък (checksum appendix).
* Позиция: `before` (преди страниците на отчета) или `after` (по подразбиране).

### Кодове за грешка

| Код | Значение |
|---|---|
| `EMBED_POSITION_INVALID` | Позицията не е `before`/`after` |
| `EMBED_PDF_SOURCE_INVALID` | Избраният за вграждане файл е невалиден |
| `EMBED_PDF_SOURCE_MISSING` | Файлът липсва |
| `{SINGLE_PDF,COMBO_PDF}_SOURCE_UNREADABLE` | PDF не може да бъде прочетен |
| `..._SOURCE_ENCRYPTED` | Шифрован PDF — отказва се преди инспекцията на подписа |
| `..._SOURCE_EMPTY` | Няма страници |
| `..._SOURCE_SIGNATURE_AUDIT_FAILED` | Инвентарът на подписите не може да бъде изготвен |

Шифроването се проверява **преди** инспекцията на подписа: иначе `pdf_preflight`
връща суров `ValueError` вместо код на конвейера.

## 6. QR код в края на отчета

Блокът е **задължителен**, не опция. В края на всеки генериран отчет (SINGLE,
COMBO и при отчет на файл) стои блок с QR код и двуезичен текст, който казва, че
кодът води до електронните документи за времевите печати в този отчет — RFC 3161
отговори за START и STOP, TSA сертификати с веригите им, CRL/OCSP статус и
OpenTimestamps доказателството. Текстът уточнява, че отчетът документира един файл
или няколко файла, че връзката доставя отчета и проверките **заедно** (един файл
или ZIP с няколко) и какво представлява `.ots` файлът. Програмата не създава OTS
доказателство — описва това, което проверяващият получава по същата връзка.

Адресът се генерира за всеки отчет: базов адрес (променлива
`CHRONOSEAL_EVIDENCE_BASE_URL` → `config['verification']['base_url']` →
`https://pasev.asuscomm.com/static/`) плюс случаен код от 37 шестнайсетични знака в
групи `10-4-4-4-15`. Същият адрес се записва в case папката и в manifest-а.

Блокът е само указател: не променя хеш, подпис или печат, а внесените оригинални
страници остават байт-за-байт. Геометрията е в `style/74_verification_qr.js`
(секция `VERIFICATION_QR`), правилата за адреса — в `chronoseal/verification_qr.py`.

| Код | Значение |
|---|---|
| `VERIFICATION_QR_INVALID` | базовият адрес не е абсолютен `http(s)` с хост |
| `VERIFICATION_QR_NOT_APPLIED` | в case папката липсва `verification-qr.json` или адресът в него е друг |

Manifest-ът получава `verification_qr`, `verification_qr_code`,
`verification_qr_url`, `verification_qr_position`, `verification_qr_record`,
`verification_qr_rendered`.

### Договор за редирект (пакет за доработване)

Кодът тук **не създава `.ots`**, не качва нищо и не поддържа редиректи. Той
отпечатва връзката и я записва в case папката, а сървърът на внедряващия трябва да
пренасочи тази една връзка към **два** документа: самия отчет и пакета с
доказателствата (RFC 3161 отговори, TSA сертификати с вериги, CRL/OCSP статус и
OTS доказателството). Затова `--url` задава хост, а не „включва QR“; адресът се
проверява предварително (`VERIFICATION_QR_INVALID` при невалиден базов адрес).

## 7. Команден ред

Входната точка е `chronoseal_report.py` (обвивка `Run_Report.bat`): една дума избира
вида отчет, входът решава режима.

| Отчет | Вход | Какво публикува |
|---|---|---|
| `SINGLE` | един файл | подпечатан отчет за файла |
| `SINGLE_PDF` | един PDF | същият, с вграден входен файл байт-за-байт |
| `COMBO` | папка **или** изричен набор файлове | отчет за набора |
| `COMBO_PDF` | папка + `--pdf` | отчет с вграден PDF преди или след отчета |
| `COMBO_ALL` | папка | отчет за папката и всички подпапки |
| `COMBO_ALL_PDF` | папка + `--pdf` | рекурсивният отчет с вграден PDF |

```powershell
python chronoseal_report.py list                    # имената и договорът за URL
python chronoseal_report.py --information           # какво очаква това издание
python chronoseal_report.py SINGLE  C:\cases\letter.pdf
python chronoseal_report.py COMBO_ALL_PDF C:\cases\2026-08 `
  --pdf C:\cases\Anlage.pdf --position before --url https://example.net/static/
```

Несъответствие име↔вход се отказва преди хеширане: `COMBO` върху файл, `SINGLE`
върху папка, `_PDF` без `--pdf`, `--pdf` при отчет без вграждане. Оркестраторът само
проверява и превежда към `chronoseal_cli.py`, затова логовете, кодовете за изход и
доказателствата са идентични с директното извикване.

Изборът на доказателствения набор:

* `--recursive` (или `COMBO_ALL`) — папката с подпапките;
* `--filter '*.eml' --filter '*.pdf'` — верижни филтри; верига без съвпадение спира с
  код `3` (`FILTER_MATCHED_NO_FILES`) и не изразходва номер на отчет;
* `--file a.pdf --file sub\b.pdf` — изричен набор; папката-цел става незадължителна
  (използва се най-дълбоката обща папка), не се комбинира с `--filter` и с рекурсия.

`--url` има приоритет пред `CHRONOSEAL_EVIDENCE_BASE_URL` и пред
`config['verification']['base_url']`; добавя се `/` в края при нужда. Пускането
отпечатва базовия адрес, генерирания код и едноредово резюме преди генериране.
Кодове за изход: `0` PASS, `2` BLOCKED, `3` филтър без съвпадение, `130` прекъсване.

## 8. JavaScript клонинг

`js/` е независим клонинг с три изисквания: същите имена на типовете, същият договор
за вградения PDF и същата структура на доказателствата.

| Модул | Роля |
|---|---|
| `js/cli.mjs` | Аргументи, режими, публикуване под окончателно име |
| `js/api.mjs` | Програмен API (`buildArgv`, `reportForFile`, `reportForFolder`, …) |
| `js/lib/report.mjs` | Тип на отчета и етикети |
| `js/lib/identity.mjs` | Име на документа и разпознаване на „собствен“ файл |
| `js/lib/embed.mjs` | Вграждане, прикачен файл, одит |
| `js/lib/reports/*.mjs` | По един модул за всеки тип |
| `js/lib/normalize.mjs` | PDF/A-2b нормализация |

Клонингът **не** подписва с DocTimeStamp — това е записано в `manifest.signature`
(`NOT SIGNED`). Затова неговите отчети не заместват подпечатаните от Python изданието.

## 9. Тестове

| Команда | Обхват |
|---|---|
| `python tests/<име>.py` | Изпълнимите тестове на Python изданието (без `tests/__init__.py`) |
| `python -m pytest tests/test_report_orchestrator.py -q` | Имената, съответствието име↔вход, `--file`/`--filter`, `--url` |
| `npm run test:clone` | `node --test js/test/` |
| `npm run test:js` | Тестове на нормализатора и JSX моста |
| `npm run test` | `unittest discover` за `tests/` и `hash_report_generator/tests` |
| `npm run verify` | Пълната верига: check, vendor, selfcheck, doctor, тестове |

Правило: всеки провален тест се пуска наново от начало, докато целият набор не стане
100% зелен; резултатът се записва в документа за надграждането.

## 10. Известни ограничения

* DocTimeStamp изисква достъп до TSA; без него отчетът остава UNSEALED и не се публикува.
* JS клонингът не подписва и не може да подмени Python изданието при правни цели.
* Вграденият PDF не се валидира криптографски — одитът само инвентаризира подписите.
* `hash_report_generator` трябва да остане самостоятелен скрипт без внос на ChronoSeal.
* Доказателствата никога не влизат в git (`.sqlite3`, генерирани отчети, архиви, `node_modules`).
