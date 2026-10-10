# GitSU v0.33 — Enterprise qualification

## Реализирани поправки
- Отделна операция за доверяване на конкретно NAS репозитори чрез `git config --global --add safe.directory <path>`, само след преглед и изрично потвърждение.
- Проверка на Git достъп преди и след промяната. Няма `safe.directory=*`.
- Експортът, отменен от потребителя, вече не се отчита като техническа грешка.
- Съхранени са останалите операции и BG/DE текстове.

## Блокиращи условия за Enterprise 1.0.0
- Реален Windows Electron GUI E2E и тест на UNC NAS собственост/SID.
- Реален GitHub PAT и Git remote E2E с отделен тестов акаунт.
- Home Assistant/HACS runtime и инсталационен тест.
- Тестове на прекъснато NAS копиране, restart/rollback и concurrency.
- Независим одит на лицензите на зависимостите и офлайн portable runtime.

**Статус: RC / BLOCKED за окончателен Enterprise release.**
