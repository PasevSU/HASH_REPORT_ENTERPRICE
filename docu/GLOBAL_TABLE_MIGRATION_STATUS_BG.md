# DEV v63 — централен табличен профил

Еталон: FILE INFORMATION. Единствен източник за цветовете, рамките, отстоянията и сянката: `hash_report_generator/style/30_tables.js`, `GLOBAL_TABLE_PROFILE` и `TABLE_RELIEF`.

Мигрирани конструктори: `hash_report_core.py` (вкл. START/STOP, FILE INFORMATION, LEGAL, TECHNICAL, SUMMARY), `modular_report.py`, `pdf_object_rules.py`, `chronoseal/page_identity.py` (checksum appendix).

**Важно:** това е целева миграция на основните ReportLab пътища, не доказателство за 100% миграция на всички legacy/HTML конструктори. Не е финален релийз.
