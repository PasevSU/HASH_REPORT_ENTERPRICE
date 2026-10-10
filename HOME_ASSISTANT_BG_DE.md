# Home Assistant / HACS — GitSU v0.27 RC

## Български

В „Операции“ избери **Home Assistant / HACS · Проверка** за статична проверка на структурата на интеграция (`custom_components/<domain>`), `manifest.json`, `__init__.py`, `config_flow.py` при `config_flow: true`, JSON преводи и `hacs.json`. Поддържат се и базови проверки за frontend (`www/`) и themes (`themes/`).

**Home Assistant · Ново репозитори** показва план и създава минимални файлове само след потвърждение, без презаписване. Шаблонът НЕ е готова работеща интеграция. Трябва да се реализира действителната логика, да се попълнят документация/автори и да се тества в Home Assistant преди публикуване. HACS и Home Assistant имат допълнителни изисквания, които този статичен валидатор не доказва.

## Deutsch

Im Vorgang **Home Assistant / HACS · Prüfen** werden Integrationsstruktur, `manifest.json`, `__init__.py`, optionale `config_flow.py`, JSON-Übersetzungen und `hacs.json` statisch geprüft. Einfache Prüfungen für `www/` und `themes/` sind ebenfalls vorhanden.

**Home Assistant · Grundgerüst** zeigt eine Vorschau und erstellt Dateien erst nach Bestätigung, ohne vorhandene Dateien zu überschreiben. Das Grundgerüst ist **keine funktionsfähige Integration**. Dokumentation, Eigentümer, Implementierung und echte Home-Assistant-Tests sind vor einer Veröffentlichung erforderlich.

## Not yet implemented / Оставащи функции

HACS release metadata checks, GitHub release/tag workflow, HA installation/update over SSH or API, automatic backup/rollback, CI runtime tests, and end-to-end HA/HACS verification. No automatic deployment is claimed.
