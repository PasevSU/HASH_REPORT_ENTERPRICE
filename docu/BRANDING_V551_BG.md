# ChronoSeal™ Enterprise v5.5.1 — брандинг на интерфейса

## Обхват

Брандингът описва **продуктовата идентичност на интерфейса**, а не съдържанието на
отчета. Затова са променени само графичните повърхности:

| Повърхност | Файл | Промяна |
|---|---|---|
| Основен прозорец (Tk) | `ChronoSeal_GUI.pyw` | хедър и локъп, навигационна релса с икони, конзоли `log`/`diag`, футър |
| Базов слой на темата | `ChronoSeal_Original_Legacy.py` | `_configure_enterprise_theme`, шрифтове, конзоли |
| Панел „Automatic Reports“ | `automation/Start_Automation.py` | списък с файлове и дневник на изпълнението |
| Панел „Selection“ | `automation/File_Filter_Panel.py` | фон на preview платното |
| Уеб справочен изглед | `ui/index.html`, `ui/style.css` | токени, локъп, златен надпис `ENTERPRISE` |

**Умишлено извън обхвата:** `hash_report_generator/style/10_palette.js` и
`hash_report_generator/style/25_font_families.js`. PDF палитрата е договор за
доказателствен документ — промяна в нея би променила golden payload хеша
`8fc6eceba632695a8b7892306bc65e9a604686c92c0a2047ef8a4dcdda28ae66` (30 749 B,
52 ключа), който се проверява от `tests/test_v90_js_rule_loader.py` и е цитиран в
release notes. Затова отчетът изглежда точно както преди надграждането, а
верификацията на вече издадени отчети остава валидна.

## Палитра

Единствен източник: `chronoseal/branding.py` → `PALETTE`. Петте роли от бранд
листа са задължителни и се проверяват от тестовете:

| Роля | Код | Употреба |
|---|---|---|
| `primary` (Основен) | `#0B1F3B` | навигационна релса, хедър, заглавия, неактивни бутони |
| `accent` (Акцент) | `#1E64D6` | активна страница, основно действие, фокус, селекция |
| `gold` (Златен) | `#D4AF37` | монограм и икона в хедъра, надпис `ENTERPRISE`, разделител |
| `background` (Фон) | `#E6EEF7` | фон на работната среда |
| `surface` (Бяло) | `#FFFFFF` | панели, карти, платна, конзолен контраст |

Производни роли (също в `PALETTE`, за да няма нито един твърдо зададен код в GUI):

| Роля | Код | Употреба |
|---|---|---|
| `primary_hover` | `#17365B` | hover на тъмните бутони |
| `rail_text` | `#C7D6E8` | текст върху `primary` |
| `rail_text_strong` | `#FFFFFF` | активен текст върху `primary` |
| `rail_rule` | `#1E3E63` | разделител в релсата |
| `accent_hover` | `#1A56BC` | hover на акцентните бутони |
| `gold_hover` | `#C39E2C` | hover на златните елементи |
| `gold_soft` | `#F2E3B0` | мек златен фон (бадж, маркер) |
| `ink` | `#0B1F3B` | основен текст върху светъл фон |
| `body` | `#1B3350` | текст в полета |
| `muted` | `#4E6480` | вторичен текст |
| `muted_soft` | `#7A8EA6` | най-слаб текст, бележки |
| `border` / `border_soft` | `#C9D7E7` / `#DCE6F2` | рамки на панели и таблици |
| `surface_alt` | `#F5F8FC` | редуващи се редове, полета за въвеждане |
| `status_bg` / `status_fg` | `#D8E4F2` / `#23405F` | статусен ред |
| `trough` | `#D3DFEE` | канал на прогреса |
| `disabled` | `#A9B9CC` | неактивен текст |
| `on_accent` | `#FFFFFF` | текст върху акцент |
| `console_bg` / `console_fg` | `#071A33` / `#D6E4F5` | конзоли `log`, `diag`, дневника на автоматизацията |
| `console_select` / `console_border` | `#1E64D6` / `#1B3B60` | селекция и рамка на конзолите |

## Типография

| Роля | Стек | Употреба |
|---|---|---|
| `ui` | Inter → Inter Variable → Segoe UI → Arial | целият интерфейс |
| `document` | Source Sans 3 → Source Sans Pro → Segoe UI → Arial | preview на отчета в уеб изгледа |
| `mono` | Cascadia Mono → Consolas → Courier New | конзоли и дневници |

`branding.resolve_family()` връща първото инсталирано семейство от стека, а ако
няма нито едно — последното (за да има винаги валиден шрифт). `FontBook` пази
резолюцията за текущия Tk интерпретатор и се използва навсякъде вместо
твърдо зададени `(`Segoe UI`, 10)` кортежи.

**Честна бележка:** на машината, на която е правен този release, Inter и
Source Sans 3 не са инсталирани, затова проверените стойности са
`{'ui': 'Segoe UI', 'document': 'Segoe UI', 'mono': 'Cascadia Mono'}`. Където
бранд шрифтовете са налични в системата, интерфейсът ги използва автоматично —
няма нужда от промяна в кода. Шрифтове не се разпространяват в архива.

## Модулни икони

Девет 16×16 монохромни маски в `GLYPHS`; рендират се като `tk.PhotoImage` с
прозрачни „дупки“, така че една и съща икона работи върху светъл и върху тъмен
фон (`branding.icon(name, size, fg, bg, master)`).

| Икона | Модул (бранд лист) | Страница |
|---|---|---|
| `report` | Отчет | `run_tab` (01) |
| `hashes` | Хешове | — (показан само в каталога на модулите) |
| `timestamp` | Времеви печат | `automation_tab` (02) |
| `signature` | Подпис | — |
| `verification` | Проверка | — (монограм в хедъра) |
| `archive` | Архив | — |
| `configuration` | Конфигурация | `set_tab` (03) |
| `journal` | Журнал | `diag_tab` (04) |
| `filter` | Филтър | `filter_tab` (05) |

## Локъп и продуктови низове

`branding.PRODUCT`:

* `vendor` — `PasevSU®`
* `product` — `ChronoSeal™`
* `badge` — `Enterprise` (златен надпис до името)
* `tagline` — `DIGITAL EVIDENCE · TIME STAMP · PDF SEAL`
* `version_label` — `v5.5.1` (съвпада с `package.json`)
* `footer` — `PasevSU® | Forensic Tools — Enterprise Solutions`
* `licence` — `Created & licensed by Home Assistant Projects · PasevSU DEV`
* `campaign` — `Part of the NO TRUST Cybersecurity volunteer campaign`

## Технически бележки

* Кеширането на иконите е **за конкретен Tcl интерпретатор**
  (`id(master.tk)` в ключа + проверка, че кешираният образ е от същия
  интерпретатор). Без това втори прозорец в един и същ процес получава
  `pyimage1` от вече унищожен root и Tk връща `image doesn't exist`.
* `PhotoImage` обектите се пазят в атрибути на прозореца (`_brand_icon`,
  `_nav_icons`), иначе garbage collector-ът ги изчиства и иконите изчезват.
* При смяна на страница иконата се подменя заедно със стила
  (`Nav.TButton` ↔ `NavSelected.TButton`), за да е четим активният раздел.
* `automation/Start_Automation.py` е контролер, не widget — затова `FontBook`
  там се закача за самия widget (`self.files`, `logrow`), а не за `self`.

## Тестове

`tests/test_branding.py` (19 теста, без изискване за дисплей, освен един
`tk.Tk()` тест, който се пропуска при липса на дисплей):

* точността на петте роли от бранд листа и пълнота на `PALETTE_ROLES`;
* всички стойности са `#RRGGBB` с главни букви;
* наличие на производните роли, които GUI използва;
* 9 икони × 16×16, по 16 реда, само `.` и `#`;
* всяка страница от `NAV_ITEMS` има икона и обратно;
* каталогът на модулите съдържа осемте бранд имена;
* `resolve_family` / `FontBook` — приоритет на бранд шрифта, регистронезависимост,
  fallback, роли `ui`/`document`/`mono`;
* `VERSION` съвпада с `package.json`, локъп низовете са точно от бранд листа;
* **нито един хекс литерал** в четирите GUI файла и наличие на
  `from chronoseal import branding`;
* `ui/style.css` съдържа петте бранд цвята и двата шрифта, `ui/index.html`
  съдържа tagline, версия и `ENTERPRISE`;
* рендиране на икона с проверка за кеша, размерите и грешките при непозната
  икона/липсващ master.

## Правило за бъдещи промени

1. Нов цвят или шрифт се добавя **само** в `chronoseal/branding.py`.
2. Никога не се въвежда хекс код в GUI файл — тестът `test_gui_surfaces_have_no_local_colour_literals` ще го хване.
3. PDF палитрата (`hash_report_generator/style/*.js`) не се пипа; ако някога се
   промени, трябва едновременно да се обновят golden хешът, `tests/test_v90_js_rule_loader.py`
   и release notes.
