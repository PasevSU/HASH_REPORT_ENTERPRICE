# ChronoSeal — единен GUI

## Стартиране

Стартирайте `Start_ChronoSeal.bat` от главната папка. Единственият основен графичен вход е `ChronoSeal_GUI.pyw`.

## Функционални раздели

- **Report & TSA** — оригиналният генератор и задължителните RFC 3161 START/STOP и проверки.
- **Automatic Reports** — самостоятелен функционален блок с избор на операция по описание, динамични настройки, избор на файлове, план, Старт, Спри и логове.
- **Settings & Trust** — настройки на генератора, Node.js, OpenSSL, TSA доставчици и доверени сертификати.
- **Diagnostics & Logs** — оригиналната диагностика и логове.

Бързи клавиши: Ctrl+1, Ctrl+2, Ctrl+3, Ctrl+4.

## Инсталиране и диагностика

Инсталирайте Python 3.12+, Node.js 22.12+ и OpenSSL. Стартирайте `Install_Windows.bat` за Python и Node зависимостите, след което `Start_ChronoSeal.bat`. `Run_Diagnostics.bat` проверява npm/runtime целостта, импорти, и двата Python test suite-а. Той не изпраща заявка към TSA.

Профилът по подразбиране използва InfoNotary QTSA за финален STOP. LOTL signer сертификатът е provision-нат от Annex на OJEU C/2026/1944 и съвпада с подписващия текущия EU LOTL; текущите EU LOTL и български TSL snapshots са локално provision-нати, а offline XMLDSig валидаторът потвърждава подписите и делегирането. Официалните InfoNotary TSP Root и Qualified TimeStamping Service CA сертификати са provision-нати и SHA-256 отпечатъците им са проверени спрямо публичния сертификатен регистър и TSL. След потвърждение за достъп премина nonce-only RFC 3161 тест и пълен синтетичен PDF START/qualified STOP/DSS/final-reopen тест; отделен PDF timestamp verifier потвърди двете марки. Доказателствата са в `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8`. Layout audit `REVIEW` е вътрешна бележка, не пречка за независимата проверка на PDF подписите/хешовете. Не е обработван потребителски отчет в този тест. HTTP адресът излага message imprint по мрежата.

The LOTL/TSL XMLDSig verifier uses the OJEU C/2026/1944 signer certificate pin and provisioned TLv6 snapshots; it confirms that the BG TSL signer is delegated by the verified LOTL pointer. The configured STOP provider is InfoNotary. A live nonce-only RFC 3161 test passed policy, request-bound OpenSSL verification, signer chain to the explicit root, TSL status at `genTime`, and fresh CRL validation (OCSP was unavailable). The complete PDF START/qualified STOP/DSS/final-reopen flow passed on a synthetic fixture, and a separate PDF timestamp-verifier CLI confirmed both signatures. Evidence is retained in `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8`, including `independent-library-verification.json`. The layout audit's `REVIEW` is a non-blocking internal presentation note. No user report was timestamped in this fixture. The endpoint is HTTP and exposes the message imprint.

За Германия eIDAS Art. 41(2) се отнася до оборима презумпция за точността на времето и целостта на обвързаните данни при действително квалифициран времеви печат. Това не доказва авторство или съдържателна истинност и не заменя квалифициран подпис или сигурен канал, когато ZPO §§ 371a/130a ги изискват. Съдът преценява конкретното доказателство и останалите процесуални изисквания. B-Trust: https://www.b-trust.bg/en/services/time-stamp-issue; CRC Trusted List: https://crc.bg/files/_en/TSL_BG.xml.

## Архитектура

`ChronoSeal_GUI.pyw` е единственият основен GUI вход. `automation/` съдържа независимия контролер и UI на автоматичните отчети, вграден като раздел в същия прозорец. `SINGLE + PDF` пази оригиналния вход побайтово като attachment; подписите му не се прехвърлят към видимите копия на страниците или към крайния отчет.
