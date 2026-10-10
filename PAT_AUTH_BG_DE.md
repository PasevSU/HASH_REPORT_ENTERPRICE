# GitHub Personal Access Token / Persönlicher Zugriffstoken

BG: Избери „GitHub · Вход с токен“, постави токена в скритото поле, натисни „Провери“ и „Изпълни“. Изисква инсталиран `gh` CLI. Токенът се подава на `gh auth login --with-token` през stdin, без аргументи на командния ред, без запис в конфигурацията и без логване. GitHub CLI управлява съхранението на удостоверяването. Използвай fine-grained PAT с минимални права. За прекратяване: `gh auth logout --hostname github.com`. Не поставяй токена в чат, URL или Git remote.

DE: „GitHub · Token-Anmeldung“ wählen, Token in das Passwortfeld einfügen, „Prüfen“ und „Ausführen“. `gh` muss installiert sein. Übergabe über stdin an `gh auth login --with-token`; GitSU protokolliert oder speichert den Token nicht. GitHub CLI verwaltet die Anmeldung. Fine-grained PAT mit minimalen Berechtigungen verwenden. Abmelden: `gh auth logout --hostname github.com`.

Security limitation: JavaScript strings cannot be guaranteed to be wiped from memory; the Electron renderer and IPC briefly hold the token. Never run on untrusted computers.
