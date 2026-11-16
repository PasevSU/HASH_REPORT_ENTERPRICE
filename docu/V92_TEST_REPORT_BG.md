# V92 — Тестов отчет

Правило: при всеки провал целият набор се пуска **от начало**, докато резултатът
не стане 100% зелен. По-долу са всички итерации, включително провалите.

## 1. Обобщение (крайно състояние)

| Набор | Команда | Резултат |
|---|---|---|
| Python (основен) | `python -m unittest discover -s tests` | **326 OK** |
| Генератор | `python -m unittest discover -s hash_report_generator/tests` | **133 OK** |
| JS клонинг | `node --test js/test/` | **50 pass / 0 fail** |
| PDF нормализация + JSX | `node --test tools/pdfnorm/test/ tools/jsx/test/` | **65 pass / 10 skipped / 0 fail** |
| GUI приемане (pytest) | `python -m pytest tests/test_ui_selection_filters.py -q` | **35 passed** |
| Vendor интегритет | `node tests/vendor_integrity.mjs` | **PASS** |
| Ръчна проверка single_pdf | `python tests/real_single_pdf_attachment_check.py` | **PASS** |

Общо: **574 автоматични теста** без нито един провал.

## 2. Итерации и отстранени дефекти

### Итерация 1 — `tests/test_combo_pdf_embedding.py`

`16/18` успешни, `2` грешки.

1. `test_embedding_an_encrypted_pdf_is_refused`
   * Симптом: суров `ValueError: Encrypted PDF: signature inspection unavailable`
     излизаше из `pdf_preflight.inspect_pdf` вместо кодирана `PipelineError`.
   * Причина: одитът на подписа се изпълняваше **преди** проверката за шифроване.
   * Поправка: в `_compose` шифроването се решава първо, а провалите се преобразуват в
     `{SINGLE_PDF|COMBO_PDF}_SOURCE_ENCRYPTED`.
2. `test_recursive_run_publishes_combo_all_pdf`
   * Симптом: очакван `..._COMBO_ALL_PDF.pdf`, получен друг.
   * Причина: **тестът** беше грешен — реалният генератор винаги пише `..._COMBO.pdf`,
     а `_ALL` и `_PDF` се добавят при публикуване.
   * Поправка: стъб генераторът вече пише `RPT-…_HASHREPORT_TYP_COMBO.pdf`.

Повторно пускане: **18/18 OK** (9.08 s).

### Итерация 2 — регресионно подмножество

`test_single_pdf_page_identity.py` (2), `test_unified_report_invariants.py` (3),
`test_volume_and_merge_regression.py` (3) — всички OK.

### Итерация 3 — `tests/real_single_pdf_attachment_check.py`

* Симптом: `AssertionError: 3` при очаквани 4 страници, плюс твърд път
  `/mnt/data/ChronoSeal_v56_A4_PROVENANCE_DEV`.
* Причина: очакването беше отпреди дизайна `preserve_pages` + приложение; реалната
  подредба е коректна (стр. 1 отчет, стр. 2 запазен оригинал 842×1282, стр. 3
  приложение с хешове).
* Поправка: преносим `sys.path` и проверка на **истинските** инварианти. Резултат: PASS.

### Итерация 4 — `tests/test_ui_selection_filters.py`

* Симптом: `python tests/test_ui_selection_filters.py` не печата нищо и излиза с 0.
* Причина: модулът използва `pytest.fixture`, тоест е pytest модул, не unittest.
* Поправка: пуска се с `python -m pytest … -q`. Резултат: **35 passed**.

### Итерация 5 — пълна регресия №1

`FAILED (failures=3)` — само `test_cli.py`:

* `test_preflight_json_is_clean_on_stdout` →
  `TypeError: FakePipeline.preflight() got an unexpected keyword argument 'combo_embed'`
* `test_legacy_flags_are_still_accepted` → `2 != 0`
* `test_run_returns_pass_and_reports_the_pdf` → `2 != 0`

Причина: стъбовете в теста пазеха старите подписи, а CLI вече подава `combo_embed`,
`embed_pdf` и `embed_position`. Поправка: подписите са приведени към реалните, `ran`
записва и двата нови аргумента, и са добавени 3 нови теста:

* `test_embed_flags_reach_the_pipeline_verbatim`
* `test_embed_position_defaults_to_after`
* `test_preflight_reports_both_embedding_routes`

Повторно пускане на `tests/test_cli.py`: **10 OK**.

### Итерация 6 — пълна регресия №2

`FAILED (failures=1)` — `test_bridge_contract.BridgeContract
.test_distinct_provider_requires_distinct_name_and_endpoint`.

Причина: **не е дефект в кода** — тестът стартира `openssl req -x509 -newkey rsa:2048`
в подпроцес; при натоварване от целия набор той е чувствителен. Пуснат самостоятелно:
**19 OK**. Потвърдено с независимо повторение на целия набор.

### Итерация 7 — пълна регресия №3

`python -m unittest discover -s tests` → **OK, 326 теста**. 100% зелен резултат.

## 3. Покрити сценарии на новото поведение

| Сценарий | Python | JS |
|---|---|---|
| COMBO + избран PDF, позиция `after` | да | да |
| COMBO + избран PDF, позиция `before` | да | да |
| Рекурсивен COMBO + PDF → `COMBO_ALL_PDF` | да | да |
| `_PDF` остава в края на името | да | да |
| Невалидна позиция | да | да |
| Двете взаимноизключващи се вграждания | да | да |
| Липсващ / нечетим / шифрован източник | да | да |
| Вграждане на самата цел | да | да |
| Геометрия и байтова идентичност | да | да |
| `per-file` + избран PDF → отказ | — | да |
| Пропускане на флаговете през CLI | да | да |
| Обвивки `COMBO_PDF.bat` / `COMBO_ALL_PDF.bat` | да | — |

## 4. Ръчни проверки на обвивките

```
COMBO_PDF.bat                      → exit 2, Usage
COMBO_ALL_PDF.bat                  → exit 2, Usage
COMBO_PDF.bat a b c middle         → exit 2, "position must be before or after"
COMBO_PDF.bat a b c after          → exit 2, "embedded PDF not found"
```

## 5. Какво не е тествано автоматично

* Истинско подпечатване с RFC 3161 срещу реален TSA — изисква мрежа и валиден
  сертификат; тестовете използват стъб/фалшив OpenSSL.
* PDF/A-2b валидация с външен валидатор — твърдението покрива само авторските
  страници, внесените се добавят след нормализацията.
