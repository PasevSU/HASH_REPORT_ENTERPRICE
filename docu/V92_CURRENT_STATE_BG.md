# V92 — Актуално състояние и работа на ChronoSeal Enterprise

Документът описва **какво прави програмата днес** (версия на Python пакета `5.7.0`
плюс надграждането за вграждане на PDF в COMBO отчети). Той е изходната точка за
надграждането, описано в `V92_UPGRADE_PLAN_BG.md`.

## 1. Два независими номера на версия

| Номер | Къде живее | Какво означава |
|---|---|---|
| `5.7.0` | `chronoseal/branding.py` (`VERSION`), `package.json`, таблицата в `README.md` | Версия на Python пакета и на GUI заобикалящата среда |
| `CLONE_VERSION` | `js/cli.mjs` (`CLONE_VERSION = '1.0.0'`), вгражда се в `manifest.implementation` | Версия на независимия JavaScript клонинг |

Двете версии се движат отделно: JS клонингът се разпространява като отделен продукт
(`js/HashReport.bat`, `js/api.mjs`) и не изисква Python.

## 2. Точки на влизане

| Вход | Файл | Предназначение |
|---|---|---|
| Един бутон (Windows) | `Start_ChronoSeal.bat` → `ChronoSeal_OneButton.py` | Стартира обединения GUI без конзола |
| Обединен GUI | `ChronoSeal_GUI.pyw` (`ChronoSealDesktop`) | Страници: Run, Selection/Filters, Settings, Diagnostics |
| Класически GUI | `ChronoSeal_Original_Legacy.py` (`App`) | Изходният едноекранен интерфейс; обединеният GUI наследява неговите помощни методи |
| Команден ред (Python) | `chronoseal_cli.py` | `--profile`, `--source`, `--output`, `--embed-pdf`, `--embed-position`, `--source-pdf`, `--explanation` |
| Неподпечатан диагностичен runtime | `chronoseal_process_cli.py` + `automation/*.bat` | Само UNSEALED JSON доказателства; изисква `--allow-unsealed-diagnostics` |
| Обвивки за вграждане | `automation/COMBO_PDF.bat`, `automation/COMBO_ALL_PDF.bat` | Подпечатан път (`chronoseal_cli.py`); приемат `INPUT OUTPUT EMBED_PDF [before|after]` |
| Обвивки без вграждане | `automation/SINGLE.bat`, `SINGLE_PDF.bat`, `COMBO.bat`, `COMBO_ALL.bat` | Само неподпечатан диагностичен runtime (`chronoseal_process_cli.py`) |
| Панел „отчет от файлове“ | `automation/Report_From_Files_Panel.py` | Избор на папка/файлове и ръчно предаване към генератора |
| Панел за филтри | `automation/File_Filter_Panel.py` | Каскадни филтри (`*eml.pdf`), всяко въведено поле отваря следващо |
| JS клонинг (CLI) | `js/cli.mjs` (`node js/cli.mjs`) | Пълен отчет без Python и без RFC3161 |
| JS клонинг (GUI) | `js/HashReport.bat` | Стартира същия клонинг с графичен избор |

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

## 6. Графичен интерфейс

Страница **Run** на обединения GUI е разделена на четири панела:

1. **Selection** — цел, режим, подпапки, индикатор за филтри.
2. **PDF embedding** — отметка, позиция `Before report` / `After report`, поле за път
   до PDF, бутон `Choose PDF`, бутон `More options…`.
3. **Output** — „Запази в друга папка“.
4. **Run and monitor** — генериране, прогрес, лог.

Опциите, които не се използват при всяко пускане (ERLAEUTERUNG, подпапки, изходна
папка, позиция, избор на PDF), живеят и в отделен диалог `Още опции… / More options…`
(`_embed_dialog`), който при отказ връща панела в предишното състояние. Панелът
остава кратко резюме, диалогът носи пълния набор — така един ред не се превръща в
шест контроли, които се застъпват при 125% мащаб.

Панелът **Selection/Filters** държи каскадните филтри: всяко въведено поле
(`*eml.pdf`) отваря следващо поле; филтрите се прилагат в реда на въвеждане и се
записват в `manifest.selection_filters`.

## 7. JavaScript клонинг

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

## 8. Тестове

| Команда | Обхват |
|---|---|
| `python tests/<име>.py` | Изпълнимите тестове на Python изданието (без `tests/__init__.py`) |
| `python -m pytest tests/test_ui_selection_filters.py -q` | Приемният GUI тест (само pytest) |
| `npm run test:clone` | `node --test js/test/` |
| `npm run test:js` | Тестове на нормализатора и JSX моста |
| `npm run test` | `unittest discover` за `tests/` и `hash_report_generator/tests` |
| `npm run verify` | Пълната верига: check, vendor, selfcheck, doctor, тестове |

Правило: всеки провален тест се пуска наново от начало, докато целият набор не стане
100% зелен; резултатът се записва в документа за надграждането.

## 9. Известни ограничения

* DocTimeStamp изисква достъп до TSA; без него отчетът остава UNSEALED и не се публикува.
* JS клонингът не подписва и не може да подмени Python изданието при правни цели.
* Вграденият PDF не се валидира криптографски — одитът само инвентаризира подписите.
* `hash_report_generator` трябва да остане самостоятелен скрипт без внос на ChronoSeal.
* Доказателствата никога не влизат в git (`.sqlite3`, генерирани отчети, архиви, `node_modules`).
