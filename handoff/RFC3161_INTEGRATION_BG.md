# RFC 3161 verification integration — DEV v28

Инсталираният пакет от потребителя е `pdf-rfc3161` **0.2.1**. Копирани са компилираната библиотека и нейните production зависимости, без промяна на `bridge/stamp.mjs` или криптографските настройки. MIT лицензът на библиотеката се запазва в `node_modules/pdf-rfc3161/LICENSE`.

## Проверка на PDF

```powershell
node .\bridge\verify_pdf.mjs --input "C:\path\report.pdf" --output "C:\path\verification.json" --root "C:\path\approved-root.pem"
```

- Доверените коренни сертификати са задължителни и се предоставят изрично; няма автоматично доверяване на сертификат от PDF.
- `PASS` изисква поне един времеви печат и успешна проверка на всички намерени.
- `NO_TIMESTAMPS`, `FAIL` и `ERROR` връщат exit code 1.
- Включени са проверки на message imprint/ByteRange, ESS, timestamp EKU и валидност към genTime чрез библиотеката; реалните OCSP/CRL проверки и независим OpenSSL път остават в стария мост и подлежат на end-to-end квалификация.
- Това е отделен verification entrypoint, а не промяна на съществуващия timestamping pipeline. Няма симулирани TSA токени.

## Непокрити release gates

Реално подпечатване с TSA и два доставчика; подписан SINGLE_PDF; визуални регресии на четирите профила; независима проверка с реален доверен сертификат; failure/restart/concurrency tests. Статус DEV / RELEASE BLOCKED.
