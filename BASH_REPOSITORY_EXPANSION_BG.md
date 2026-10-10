# GitSU v0.38 — Repository command coverage

Разширен allowlist: show, reflog, fsck, count-objects, ls-files, ls-tree, show-ref, remote-show, submodule-status, worktree-list, stash-show, shortlog, config-list-local, config-get, remote-rename, branch-delete, merge-ff, revert-commit, stash-apply, submodule-init, submodule-sync, maintenance-run, gc, config-set-local.

Изрично потвърждение `GITSU_MUTATION_CONFIRMED=YES` за операции с промени. Няма свободно подаване на shell аргументи. GitHub CLI (gh repo/pr/issue/release/workflow) не е имплементиран в този Bash скрипт и изисква отделен контролиран изпълнител. Скриптът не е свързан с всички GUI бутони.

Внимание: `git config --local --list` може да съдържа чувствителни данни (например URL с токен); не публикувайте журналите без редактиране.
