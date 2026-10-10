# GitSU Watcher — Home Assistant / Linux

Изисквания: `bash` и `git` (HA add-on/контейнер, напр. Terminal & SSH add-on; HAOS Core не е подходящ).

1. Разархивирайте в `/config/gitsu-watcher/` (или друга постоянна папка).
2. `cp watcher.env.example watcher.env`, задайте `REPO_PATH` (напр. `/config`) и SSH ключ/токен за `origin`.
3. Dry run: `bash start-watcher.sh`
4. Реален режим: `APPLY=1` в `watcher.env`.
5. Автостарт: в Terminal & SSH add-on → `init_commands`: `nohup bash /config/gitsu-watcher/start-watcher.sh >/dev/null 2>&1 &`, или `shell_command`/автоматизация при старт на HA.

Поведението, състоянията, журналът и блокировките са идентични с Windows варианта (виж README-windows.md). Журнал: `<repo>/.git/gitsu-watcher.log`.

Ограничение: не използвайте два writer-а (Windows + HA) към един и същ клон.

## Windows <-> HA (lease)
С `APPLY=1` двата възела (Windows и HA) координират записа чрез lease ref `refs/gitsu/lease/<branch>` в origin.
Само държателят commit-ва/push-ва; другият е `FOLLOWING` и прави `merge --ff-only`. При спрял/паднал възел
другият поема след `LEASE_TTL + LEASE_GRACE` секунди. Часовниците трябва да са синхронизирани (NTP).
Проверка: `--lease-status` (sh) / `-Mode lease-status` (ps1); принудително освобождаване: `--lease-break` / `-Mode lease-break`.
Не-държателят не публикува локални промени - редактирайте на активния възел.
