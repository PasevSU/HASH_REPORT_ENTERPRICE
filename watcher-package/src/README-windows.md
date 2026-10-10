# GitSU Watcher — Windows

Изисквания: PowerShell 7 (`pwsh`) и Git. Разархивирайте където и да е.

1. Копирайте `watcher.env.example` → `watcher.env`, задайте `REPO_PATH` (UNC пътища са позволени).
2. Тест (dry run, по подразбиране `APPLY=0`): `start-watcher.cmd`
3. Реален режим: `APPLY=1` в `watcher.env`.
4. Автостарт при вход: `pwsh install-task.ps1` (премахване: `-Remove`).

Поведение: следи само проследявани файлове → debounce → `fetch` → отказ при отдалечена промяна (CONFLICT) → `git add -u` → проверка за тайни (ключове, токени, `.env`, `*.pem`) → commit → push → проверка чрез `git ls-remote`, че отдалеченият SHA съвпада (VERIFIED). При грешка — експоненциално забавяне до `MAX_BACKOFF`.

Състояния в журнала: IDLE, CHANGED, STABILIZING, FETCHING, CONFLICT, COMMITTING, PUSHING, VERIFIED, FAILED. Журнал: `.git/gitsu-watcher.log` (ротация 1 MB).

Блокировки: `.git/gitsu-watcher.lock` (един наблюдател; остарялата блокировка след срив се възстановява автоматично по PID) и `.git/gitsu-op.lock` (кратка блокировка на записа, споделена с GUI).

Ограничение: не използвайте два writer-а (Windows + HA) към един и същ клон; няма разпределена координация.

## Windows <-> HA (lease)
С `APPLY=1` двата възела (Windows и HA) координират записа чрез lease ref `refs/gitsu/lease/<branch>` в origin.
Само държателят commit-ва/push-ва; другият е `FOLLOWING` и прави `merge --ff-only`. При спрял/паднал възел
другият поема след `LEASE_TTL + LEASE_GRACE` секунди. Часовниците трябва да са синхронизирани (NTP).
Проверка: `--lease-status` (sh) / `-Mode lease-status` (ps1); принудително освобождаване: `--lease-break` / `-Mode lease-break`.
Не-държателят не публикува локални промени - редактирайте на активния възел.
