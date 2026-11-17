# V93 — PDF вграждане за COMBO отчети и разделени опции (5.8.0)

Документът описва **какво прави програмата днес** (версия `5.8.0`) при вграждане
на PDF. Правилата за тип отчет и позиция са изнесени в един модул, а опциите,
които преди стояха в един претъпкан диалог, са разделени по теми.

## Какво се промени

| Преди | Сега |
|---|---|
| Един диалог `Още опции…` (820x430) с вграждане, ERLAEUTERUNG, подпапки и изходна папка | Два диалога: `Вграждане…` (само PDF) и `Отчет…` (останалите опции) |
| Вграждане само на страница `Run` | Вграждане и на страница `Report from Files` (COMBO отчет от избрани файлове) |
| Уеб таблото познаваше 4 типа отчет | Познава всички 6 типа, с избор на позиция за типовете `_PDF` |
| Правилата за тип/позиция се преповтаряха в GUI и CLI | Един източник: `chronoseal/embed_options.py` |

## Един източник на правила

`chronoseal/embed_options.py` отговаря на три въпроса, които всеки прозорец
трябва да реши **преди** пускането на реален процес:

* кой тип отчет произтича от текущата селекция — `report_type_for()`;
* допустима ли е избраната позиция — `normalise_position()`;
* какво точно ще се вгради — `resolve_embed_options()`.

`Pipeline.run` остава единственият, който решава какво се записва в PDF.
Модулът само предсказва резултата, така че надписът в интерфейса и публикуваният
тип не могат да се разминат.

```python
from chronoseal.embed_options import resolve_embed_options, summary_text

options = resolve_embed_options(
    enabled=True, position="before", path=r"C:\cases\Anlage.pdf",
    target=r"C:\cases\2026-08", recursive=False,
)
options["report_type"]          # 'COMBO_PDF'
summary_text(options, "bg")     # 'COMBO_PDF · преди · Anlage.pdf'
```

Отказът е изключение `EmbedOptionError` с `code` (`position`, `single_not_pdf`,
`no_pdf`, `pdf_invalid`), за да може всеки прозорец да го преведе на своя език:
legacy прозорецът е български (`embed_language = 'bg'`), страниците на
`ChronoSeal_GUI.pyw` са английски (`embed_language = 'en'`).

### Флагът `file_list`

При `Report from Files` целта е папката с доказателствата, но отчетът е COMBO от
изрично избраните файлове. Без `file_list=True` папка с един PDF щеше да се
превърне в `SINGLE_PDF`. Затова:

```python
resolve_embed_options(..., target=evidence_root, file_list=True)["report_type"]
# 'COMBO_PDF' (или 'COMBO_ALL_PDF' при рекурсия)
```

## Разделени диалози

`PDF embedding…` (760x370) съдържа само предмета на вграждането: ключ, позиция
`Before report` / `After report`, път до PDF, кратка бележка за SINGLE входа и
реда „Какво ще се получи“. `Report options…` (720x300) съдържа ERLAEUTERUNG,
включването на подпапките и изходната папка. Всяко отваряне помни началното
състояние, така че `Cancel` връща и трите променливи, а `OK` валидира през
същите правила и показва отказан избор като модален прозорец, вместо да остави
половинчат избор.

## COMBO отчет от избрани файлове

Страница `Report from Files` има секция `3 - PDF embedding (optional)`:

* ключ `Embed a PDF in this combo report`;
* избор `Before report` / `After report`;
* бутон `PDF embedding…`, който първо предава селекцията на `Report & TSA`
  (за да описва диалогът именно този COMBO отчет) и после отваря диалога;
* ред за предсказание, който се обновява при всяка промяна.

Бутонът за вграждане е активен и при празен списък, но отваря диалога само след
като има избрани файлове, защото без тях няма COMBO отчет, в който да се вгражда.
`Create combo report` подава избора към `_run_args[8]` (PDF) и `_run_args[9]`
(позиция), точно както го прави страницата `Report & TSA`.

## Уеб табло

`ui/app.js` изброява `SINGLE`, `COMBO`, `SINGLE_PDF`, `COMBO_PDF`, `COMBO_ALL`,
`COMBO_ALL_PDF`; за типовете с наставка `_PDF` се показва избор на позиция, който
се записва в `manifest.embed.position`. Това е конфигурация на бъдещ процес —
реалното генериране остава в Python генератора и в JS клона (`js/`).

## Тестове

* `tests/test_embed_options.py` — типове отчет, позиции, откази, `file_list`,
  резюме на два езика;
* `tests/test_ui_report_from_files.py` R18–R20 — секцията за вграждане,
  отварянето на диалога от страницата и подаването на PDF + позиция към процеса;
* `tests/test_combo_pdf_embedding.py` — непроменени правила на процеса;
* `tests/test_branding.py` — версията `5.8.0` е еднаква в `package.json`,
  `chronoseal/branding.py`, `ui/` и `README.md`.
