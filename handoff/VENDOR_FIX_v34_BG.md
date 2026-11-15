# DEV v34 — устойчиво локално пакетиране на pdf-rfc3161

- Премахната е зависимостта от registry версия 0.2.0: `package.json` използва `file:vendor/pdf-rfc3161` (upstream 0.2.1).
- И двата runtime entrypoint-а `dist/index.js` (ESM) и `dist/index.cjs` (CommonJS) са поправени, както в vendor/, така и в приложената node_modules инсталация.
- `npm install` от директорията на проекта трябва да използва локалния пакет; изпълнете `npm run verify:vendor` след инсталиране.
- Манифестът съдържа SHA-256 за двата entrypoint-а.
- Корекцията е в vendored компилирания пакет, **не** е интегрирана в оригиналните TypeScript source файлове. Изходният upstream build и реалният проблемен PDF все още не са проверени.
- Не е потвърден реален RFC3161 START/STOP end-to-end; Enterprise release остава BLOCKED.
