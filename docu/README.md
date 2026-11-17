# ChronoSeal — CLI издание (5.10.0-cli)

Това е **CLI изданието** (`release/cli`): без графичен интерфейс, с оркестратор на
отчетите по име и със задължителен QR блок в края на всеки отчет. Графичното издание,
без QR код и подходящо за бързи действия и изпращане по имейл, е в клона
`release/gui`. Подробности — `V95_CLI_EDITION_BG.md`.

## Стартиране

```powershell
:: от главната папка; Run_Report.bat обвива chronoseal_report.py
Run_Report.bat list
Run_Report.bat --information
Run_Report.bat SINGLE      D:\cases\letter.pdf
Run_Report.bat COMBO       D:\cases\2026-08
Run_Report.bat COMBO_ALL_PDF D:\cases\2026-08 --pdf D:\cases\Anlage.pdf --position before --url https://example.net/static/
```

`Install_Windows.bat` не стартира нищо — отпечатва имената на отчетите и пример за
употреба.

## Имена на отчетите

| Отчет | Вход | Какво публикува |
|---|---|---|
| `SINGLE` | един файл | подпечатан отчет за файла |
| `SINGLE_PDF` | един PDF | същият, с вграден входен файл байт-за-байт |
| `COMBO` | папка или изричен набор файлове | отчет за набора |
| `COMBO_PDF` | папка + `--pdf` | отчет с вграден PDF преди/след отчета |
| `COMBO_ALL` | папка | отчет за папката и всички подпапки |
| `COMBO_ALL_PDF` | папка + `--pdf` | рекурсивният отчет с вграден PDF |

## Функционални блокове

- **Отчет и RFC 3161** — генераторът, задължителните START/STOP печати и проверките;
  извиква се през `chronoseal_cli.py <файл-или-папка>`.
- **Автоматични отчети** — `automation/*.bat` (SINGLE, SINGLE_PDF, COMBO,
  COMBO_ALL, COMBO_PDF, COMBO_ALL_PDF); неподпечатаните изискват
  `--allow-unsealed-diagnostics`.
- **Настройки и доверие** — `config/config.json`, TSA доставчици и доверени
  сертификати; `chronoseal_cli.py --bootstrap-trust` и `--self-check`.
- **Диагностика и логове** — `Run_Diagnostics.bat`, `--preflight`, `--log-dir`.
- **Избор на доказателства** — `--filter '*.eml' --filter '*.pdf'` (верижни филтри,
  код `3` при нула съвпадения) и `--file` за изричен набор.

## Договор за връзката от QR кода

Кодът не създава `.ots` и не качва нищо. Отпечатва връзката (базов адрес от `--url`,
`CHRONOSEAL_EVIDENCE_BASE_URL` или `config['verification']['base_url']` плюс генериран
код) и я записва в case папката. Сървърът на внедряващия трябва да пренасочи тази
една връзка към **два** документа: отчета и пакета с доказателствата.

## Инсталиране и диагностика

Инсталирайте Python 3.12+, Node.js 22.12+ и OpenSSL. `Install_Windows.bat` проверява
инструментите, инсталира зависимостите, заключва и проверява Node пакета и пуска
`chronoseal.selfheal`. `Run_Diagnostics.bat` проверява npm/runtime цялостта, импорти,
и двата Python test suite-а. Той не изпраща заявка към TSA.

Тестовете се пускат директно с `python -m unittest discover -s tests` и `python -m unittest discover -s hash_report_generator/tests` (или с pytest). Не използвайте `npm test` / `npm run verify`, когато работната папка е UNC път (`\\СЪРВЪР\дял\...`): Windows стартира `cmd.exe` в `C:\Windows`, `-s tests` се резолвва през `sys.path` към чужд пакет `tests` от `site-packages` и гейтът измерва чужди тестове. `npm run doctor` и `npm run verify:vendor` падат по същата причина.

Профилът по подразбиране използва InfoNotary QTSA за финален STOP. LOTL signer сертификатът е provision-нат от Annex на OJEU C/2026/1944 и съвпада с подписващия текущия EU LOTL; текущите EU LOTL и български TSL snapshots са локално provision-нати, а offline XMLDSig валидаторът потвърждава подписите и делегирането. Официалните InfoNotary TSP Root и Qualified TimeStamping Service CA сертификати са provision-нати и SHA-256 отпечатъците им са проверени спрямо публичния сертификатен регистър и TSL. След потвърждение за достъп премина nonce-only RFC 3161 тест и пълен синтетичен PDF START/qualified STOP/DSS/final-reopen тест; отделен PDF timestamp verifier потвърди двете марки. Доказателствата са в `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8`. Layout audit `REVIEW` е вътрешна бележка, не пречка за независимата проверка на PDF подписите/хешовете. Не е обработван потребителски отчет в този тест. HTTP адресът излага message imprint по мрежата.

The LOTL/TSL XMLDSig verifier uses the OJEU C/2026/1944 signer certificate pin and provisioned TLv6 snapshots; it confirms that the BG TSL signer is delegated by the verified LOTL pointer. The configured STOP provider is InfoNotary. A live nonce-only RFC 3161 test passed policy, request-bound OpenSSL verification, signer chain to the explicit root, TSL status at `genTime`, and fresh CRL validation (OCSP was unavailable). The complete PDF START/qualified STOP/DSS/final-reopen flow passed on a synthetic fixture, and a separate PDF timestamp-verifier CLI confirmed both signatures. Evidence is retained in `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8`, including `independent-library-verification.json`. The layout audit's `REVIEW` is a non-blocking internal presentation note. No user report was timestamped in this fixture. The endpoint is HTTP and exposes the message imprint.

За Германия eIDAS Art. 41(2) се отнася до оборима презумпция за точността на времето и целостта на обвързаните данни при действително квалифициран времеви печат. Това не доказва авторство или съдържателна истинност и не заменя квалифициран подпис или сигурен канал, когато ZPO §§ 371a/130a ги изискват. Съдът преценява конкретното доказателство и останалите процесуални изисквания. B-Trust: https://www.b-trust.bg/en/services/time-stamp-issue; CRC Trusted List: https://crc.bg/files/_en/TSL_BG.xml.

## Брандинг на интерфейса

Интерфейсът използва идентичността **ChronoSeal™ Enterprise v5.7.1**
(`#0B1F3B` основен, `#1E64D6` акцент, `#D4AF37` златен, `#E6EEF7` фон, `#FFFFFF`
панели; Inter за интерфейса и Source Sans 3 за документи). Всички цветове,
шрифтове, икони и продуктови низове живеят на едно място —
`chronoseal/branding.py` — и се четат от главния прозорец, от панела за
автоматични отчети, от панела Selection и от уеб справочния изглед в `ui/`.

PDF палитрата на отчета **не е променена** — брандингът е само за интерфейса,
за да остане golden payload хешът и верификацията на вече издадени отчети
непроменена. Пълното описание (палитра по роли, типография, деветте модулни
икони, локъп, тестове и правила за бъдещи промени) е в
[BRANDING_V551_BG.md](BRANDING_V551_BG.md).

## Архитектура

`ChronoSeal_GUI.pyw` е единственият основен GUI вход. `automation/` съдържа независимия контролер и UI на автоматичните отчети, вграден като раздел в същия прозорец. `SINGLE + PDF` пази оригиналния вход побайтово като attachment; подписите му не се прехвърлят към видимите копия на страниците или към крайния отчет.

## Интеграция с hAPI (Home Assistant)

Отчетите могат да се пускат и като бутони в Home Assistant през hAPI Enterprise
add-on-а (`/admin/api/v2/reports/render` и `/reports/package`). Практическото
описание — портове, токен, манифест, `shell_command`, скрипт и карти на таблото,
проверени сценарии и какво hAPI прави, а този клонинг не — е в
[HAPI_REPORT_BUTTONS_BG.md](HAPI_REPORT_BUTTONS_BG.md).

Разделението е ясно: hAPI носи реален RFC 3161 печат, CMS/PGP подпис и
доказателствен пакет, но покрива само четирите типа `SINGLE`, `COMBO`,
`COMBO_ALL` и `VOLUME`. Типовете `SINGLE + PDF` и `FILE_INFORMATION_REPORT`
остават изключително в този клонинг.
