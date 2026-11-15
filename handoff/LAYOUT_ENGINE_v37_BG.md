# DEV v37 — COMBO table layout engine

- Единен седемколонен профил в style/30_tables.json.
- Единни функции за дати, пълни SHA-256 и XML-safe имена в combined_table_layout.py.
- Прилага се както в hash_report_combined.py, така и в bridge/helper_enabled.py.
- Размери в точни bytes, а не закръглени KB.
- Повтарящ се контрастен header и общ TableStyle.
- Няма промени в RFC 3161, подписи, сертификати или криптографски код.
- DEV; за release се изискват реални PDF регресии на четирите профила и независима TSA проверка.
