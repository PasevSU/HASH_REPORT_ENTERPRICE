# ChronoSeal Enterprise — Verification Gate v29

Нова независима, **само четяща** стъпка след съществуващия `bridge/stamp.mjs`.
Не се променят `stamp.mjs`, PDF стиловете, отчетните профили или TSA конфигурацията.

Пример от корена на проекта:

```powershell
python bridge/verification_gate.py --input "report.pdf" --output "report.verify.json" --root "trusted-root.pem"
```

Gate изисква успешен резултат от `verify_pdf.mjs`, минимум два проверени времеви печата,
изрично предоставен доверен корен, съвпадащ SHA-256 на PDF и непроменен файл през проверката.
При неуспех резултатът е BLOCKED и exit code 1 или 2.

## Граници

Това не доказва end-to-end TSA квалификация без реален удостоверен PDF и доверени корени.
Не проверява семантичния START→модули→STOP процес, OCSP/CRL freshness или всички PDF визуални правила.
`verify_pdf.mjs` използва реалния `pdf-rfc3161` verifier; този gate валидира резултата му,
а не го замества. Production release остава BLOCKED.
