# DEV v58 — централизирани Unicode шрифтове и десен footer

- Централен източник: `hash_report_generator/style/25_font_families.js` за всички роли regular/bold/italic/bold_italic/monospace/monospace_bold. Използва системните Windows Arial/Consolas и Linux DejaVu; не включва бинарни шрифтове.
- `pdf_object_rules.font_name()` регистрира шрифтовете от централната конфигурация, отказва без наличен Unicode TTF. Рендерерите, които използват `font_name`, наследяват правилото.
- `chronoseal/page_identity.py` използва същата регистрация за всички footer и appendix страници.
- `style/96_page_identity.js`: 1 mm от десния физически край (вместо 20 mm) за целия десен footer блок.
- 73/73 теста PASS; Python compileall PASS.
- Реално генериран двустраничен PDF: Unicode кирилица PASS, петте footer реда завършват на x≈592.4 pt при ширина 595.28 pt; embedded DejaVuSans PASS.
- Не е доказано, че ВСЕКИ legacy/HTML renderer използва `font_name`; глобален end-to-end audit остава BLOCKED. Не са тествани TSA операции.
