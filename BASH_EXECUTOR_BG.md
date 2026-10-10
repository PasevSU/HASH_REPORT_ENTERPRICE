# GitSU — безопасен Bash изпълнител (v0.36, пилот)

`data/app/scripts/git-safe.sh` приема **операция, директория и незадължително име на remote**, без `eval`, `bash -c` или свободни Git аргументи.

Поддържа: `status`, `branch`, `log`, `remote`, `diff`, `fetch`, `pull-ff`, `push`, `trust-check`, `trust-add`.

Пример (Git Bash):

```bash
bash data/app/scripts/git-safe.sh status '//PASEVCLAUD/HDD (at HDD)/PROJECT/_js_project_pak'
bash data/app/scripts/git-safe.sh fetch '//PASEVCLAUD/HDD (at HDD)/PROJECT/_js_project_pak' origin
```

Доверяване само след изрично потвърждение в доверен интерфейс:

```bash
GITSU_TRUST_CONFIRMED=YES bash data/app/scripts/git-safe.sh trust-add '/path/to/repo'
```

**Сигурност:** `trust-add` променя потребителската Git конфигурация и трябва да се предлага само след показване на реалния път и предупреждение. Никога не го изпълнявайте автоматично. `pull-ff` изисква чисто работно дърво; `push` публикува текущия клон. Git credential manager може да се използва, но не въвеждайте токени в аргументите на командния ред.

**Ограничения:** този пакет добавя изпълнителя и тестове, но **не пренасочва съществуващите Electron IPC операции към него**. Това изисква отделна миграция с end-to-end тестове; настоящите GUI операции продължават да използват стария backend. Windows/Git Bash и NAS не са тествани тук. Няма гаранция за пълна защита от злонамерено репозитори или от промяна на папката между проверката и операцията.
