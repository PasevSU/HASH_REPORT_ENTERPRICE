# v74 — частична миграция, RELEASE BLOCKED

Мигрирани са стиловете на клетките за CRYPTOGRAPHIC TIMESTAMP START/STOP от hash_report_core.py към style/32_timestamp_cells.js, през pdf_object_rules.timestamp_cell_paragraph_style(). Запазени са буквално Helvetica-Bold, WORD/CJK, splitLongWords=1, spaceBefore=0, spaceAfter=0. Размерът и междуредието все още идват от ReportConstants и изискват последваща централизация.

73/73 unit tests PASS. Python compileall PASS. Пълни реални Enterprise профили и TSA НЕ СА проверени. Пълна миграция НЕ Е постигната.
