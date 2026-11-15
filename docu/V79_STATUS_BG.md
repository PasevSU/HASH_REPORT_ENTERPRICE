# ChronoSeal DEV v79 — частична миграция

Трите ParagraphStyle конфигурации на комбинираната таблица (SafeStyle, HashStyle2, HeaderStyle2) са преместени от `hash_report_combined.py` в `style/33_combined_cells.js`, като `pdf_object_rules.combined_cell_paragraph_styles()` ги прилага. Запазени са наследяването на стилове, wordWrap, fontSize, leading, alignment и цвят.

Проверки: 78/78 unittest PASS, компилация PASS, сравнени са реалните свойства на трите ParagraphStyle обекта със старите дефиниции.

Не е проведен end-to-end криптографски тест, визуално сравнение с еталонния PDF или доказана пълна миграция на петте блока. Статус RELEASE BLOCKED.
