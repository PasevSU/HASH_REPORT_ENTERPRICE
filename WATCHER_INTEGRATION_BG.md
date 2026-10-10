# GitSU v0.42 — Watcher с lease (Windows ↔ HA)

**Актуално:** при `APPLY=1` и `LEASE!=0` само един възел държи write-lease (`refs/gitsu/lease/<клон>`, compare-and-swap, TTL ≥ 15 с, takeover след изтичане + 30 с). Другите са FOLLOWING (`merge --ff-only`). Нужен е NTP. Команди: `lease-status`, `lease-break` (или бутоните в панел „Синхронизация“). Локален lock `<gitdir>/gitsu-op.lock` се споделя между GUI и watcher. Тестван с два възела (`tests\watcher-lease.test.js`); реален HA/SMB E2E не е квалифициран. Забележките за „няма distributed lease“ по-долу са остарели.

---
# (по-старо) v0.39 — Интегриран автоматичен Watcher (RC)

GUI: изберете регистриран репозитори → Repository Watcher → **Watch selected (dry run)** за безопасен мониторинг; **Auto commit + push** само след изрично потвърждение; **Stop** спира локалния процес.

Архитектура: Electron GUI → IPC с проверка на регистрираната папка → AutoSyncManager → PowerShell 7 (Windows) / Bash (Linux) → Git. Изходът се връща в GUI журнала. Скриптовете работят и самостоятелно чрез `node data/app/scripts/ha-git-sync.mjs`.

**Ограничения**: локалният lock не е разпределен между две копия на репозитория. Не активирайте два writer-а към един и същи GitHub клон. Автоматичният режим е изключен при стартиране и след рестарт. Няма secret scanner, distributed lease, проверка на отдалечения SHA след push, Windows/SMB/HA E2E qualification. При git commit hooks може да се изпълни код от самото репо. При съмнение ползвайте dry-run. `git add -u` не добавя непознати файлове, но може да качи чувствителни вече проследявани файлове.

**Windows**: необходим е PowerShell 7 (`pwsh`), Git и Node/Electron. **HA**: необходим е add-on/container с Git/Bash/Node; HAOS Core не е подходящ за произволни `apk add` операции.

Пакетът е Release Candidate, не сертифициран Enterprise release.
