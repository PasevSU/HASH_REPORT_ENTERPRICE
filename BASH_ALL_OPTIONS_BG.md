# GitSU v0.37 — Bash операции

Всички Git команди са изпълними през `data/app/scripts/git-safe.sh`, без `eval` и без произволни Git аргументи. Списък: status, fetch, pull-ff, push, branch, branches, log, remote, diff, diff-cached, verify, stash-list, stash-push, stash-pop, add-all, commit, switch, create-branch, tag-list, tag-create, remote-add, remote-set, remote-remove, reset-soft, restore, restore-staged, rebase-ff, clone, trust-check, trust-add.

Пример: `bash git-safe.sh status /path/to/repo` или `bash git-safe.sh commit /path/to/repo "Commit message"`.

За trust-add се изисква GITSU_TRUST_CONFIRMED=YES. За разрушителни операции се изисква GITSU_MUTATION_CONFIRMED=YES. Това не заменя интерактивно потвърждение в GUI. Някои операции като stash-pop могат да доведат до конфликти. Няма автоматичен rollback.

**Важно:** Не-Git действията (GitHub вход, export, copy, Home Assistant scaffold/validate, workflow) продължават да използват съществуващите JavaScript/Python модули. Bash не е свързан с всички GUI бутони. Няма проведени Windows/NAS E2E тестове. Пакетът е RC.
