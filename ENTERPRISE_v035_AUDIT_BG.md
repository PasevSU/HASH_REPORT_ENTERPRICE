# GitSU v0.35 — проверка на целостта на Git операции

## Корекции
- `inspect()` вече не маскира `dubious ownership` като „няма Git репозитори“. Показва насочваща грешка към операцията Git доверие.
- След GitHub Link, Push, Update и Git Trust се изисква реално потвърден Git repository статус; липсата на такъв блокира съобщение за успех.
- Добавен е регресионен тест за отказа при съмнителна собственост.

## Ограничения / release gate
- Това **не е** Enterprise 1.0.0: липсват Windows/NAS end-to-end, GitHub реални credential тестове, Home Assistant runtime/HACS тестове, crash-consistent recovery и реален Git stdout/stderr streaming.
- Няма автоматично заобикаляне на Git safe.directory защитата.
