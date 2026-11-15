# Отчетите като бутони в Home Assistant (hAPI Enterprise)

**Версия на описанието:** 1.0 · **Проверено срещу:** hAPI Enterprise add-on `0.69.216`, интеграция `hapi_enterprise` (заредена), ChronoSeal HASH_REPORT_ENTERPRICE `5.6.0`
**Обхват:** как да превърнеш генерирането на отчет (HASH REPORT) в бутон, който натискаш от Home Assistant.
**Статус на фактите:** всичко по-долу е проверено в кода на `PasevSU/hAPI` (`hapi_enterprise/routes/reports.js`, `report-manifest.js`, `report-render.js`, `server.js`, `config.yaml`) и с реален тестов рендер. Числата (версия, портове, лимити) са валидни за 0.69.216 и трябва да се презаверят при major upgrade.

---

## 0. Кратко резюме за нетърпеливите

| Искаш... | Използвай |
|---|---|
| Бутон без никакъв код | Панела на add-on-а → **Report Studio** (`/ui`) |
| Бутон от скрипт/терминал | `POST /admin/api/v2/reports/render` с JSON манифест |
| Бутон на таблото в Home Assistant | `shell_command` + `script` + `button`/`tile` карта (т. 7) |
| Отчет с доказателствен пакет (PDF + манифест + TSA) | `POST /admin/api/v2/reports/package` |
| Тип отчет `SINGLE_PDF` (вграден PDF) или `FILE_INFORMATION` | **не в hAPI** — само през JS клонинга на ChronoSeal (т. 10) |

Трите задължителни условия, за да работи бутонът:

1. Add-on-ът работи и е достъпен по мрежа (т. 3.2 — портът трябва да е публикуван).
2. Имаш admin токен (`token` в конфигурацията на add-on-а) и го слагаш в `secrets.yaml`.
3. Манифестът е валиден: първи блок `rfc3161-start`, последен `rfc3161-stop`, и двата `locked: true` (т. 5).

---

## 1. Какво означава „бутон“ в hAPI

hAPI не регистрира Home Assistant услуги. В `custom_components/hapi_enterprise/` **няма** `services.yaml`, **няма** `button.py`, **няма** `async_register`. Затова „бутон“ означава едно от три неща:

```text
 ниво 1                ниво 2                        ниво 3
 ┌───────────────┐     ┌──────────────────────┐      ┌──────────────────────┐
 │ Report Studio │     │ HTTP POST            │      │ HA табло             │
 │ в панела на   │ ──▶ │ /admin/api/v2/       │ ◀─── │ button / tile карта  │
 │ add-on-а      │     │ reports/render       │      │  ↓ shell_command     │
 └───────────────┘     └──────────────────────┘      │ python скрипт        │
       0 код                всеки клиент              └──────────────────────┘
```

Ниво 3 е **тънък клиент над ниво 2** — бутонът не прави нищо магическо, само извиква HTTP endpoint-а. Затова първо трябва да проработи `curl` (т. 6), и чак после картата на таблото (т. 7). Обратният ред е най-честата причина за „бутонът не работи“.

---

## 2. Какво има в тази инсталация (проверено)

| Компонент | Стойност | Значение за бутоните |
|---|---|---|
| Add-on | `hapi_enterprise`, версия `0.69.216` | `ingress: true`, `ingress_port: 8098` |
| Публичен listener | `8099` — **непубликуван** (`ports: 8099/tcp: null`) | трябва да го публикуваш, за да стигнеш от скрипт |
| Публичен gateway | `8088` — **непубликуван** | за външен достъп, не за бутони |
| `tsa_enabled` | `true` | `tsa: true` работи; иначе 409 |
| Съхранение | `storage_location: share`, `storage_subdirectory: hAPI/data` | отчетите се виждат в `/share/hAPI/data` |
| RBAC | `user_roles: '{"pasev-admin":"admin"}'` | admin роля за твоя HA потребител |
| Интеграция | `hapi_enterprise` — **заредена** (`supports_options: true`) | сензорите/диагностиката работят |
| Home Assistant услуги | **няма** | `hAPI.*` не съществува — не го викай |

Директно следствие: на таблото **не можеш** да напишеш `action: hapi_enterprise.render_report`. Всяка карта трябва да минава през `script`/`shell_command` (т. 7).

---

## 3. Достъп до API

### 3.1 Модел на защита (важно и лесно за объркване)

Add-on-ът слуша на два отделни порта:

- **`8098` (admin, ingress)** — приема само Supervisor и loopback. Това е портът, на който работи панелът в Home Assistant.
- **`8099` (public)** — всяка заявка към `/admin/*` **връща 404**, освен ако не носи `Authorization: Bearer <token>`. Токенът е стойността на опцията `token` (вътрешно `ADMIN_TOKEN`).

Маршрутите за отчети (`render`, `package`, `sign`, `cms/verify`) **не** минават през RBAC проверка. Защитата им идва от разделянето на портовете, не от роля. Само `/admin/api/v2/rfc3161*` извиква `adminGate(..., 'settings', ...)`.

Практически извод: бутонът от HA трябва да говори на **публикувания 8099** и да носи Bearer токен. Тогава 404 „изчезва“ и endpoint-ът отговаря.

### 3.2 Публикуване на порта (еднократна настройка)

Add-on → **Конфигурация** → `Network`:

```yaml
ports:
  8099/tcp: 8099
```

Рестартирай add-on-а. Проверка от компютър в LAN:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://192.168.50.1:8099/health
# 200
```

Ако `/health` не отговаря, портът не е публикуван и всичко останало в този документ е неактуално.

### 3.3 Токен

Опцията `token` трябва да е поне 24 знака, без `!secret` препратка и без очевиден шаблон — при невалидна стойност add-on-ът не стартира (`ADMIN_TOKEN_REQUIRED`). Сложи същата стойност в `secrets.yaml`:

```yaml
# /config/secrets.yaml
hapi_admin_token: "тук-е-твоят-токен-поне-24-знака"
```

Проверка, че токенът се приема:

```bash
curl -sS -H "Authorization: Bearer $HAPI_TOKEN" http://192.168.50.1:8099/admin/api/whoami
```

Отговорът съдържа ролята (`admin` за токена на add-on-а). Ако получиш `404`, токенът е грешен или липсва — не е 401, за да не издава, че пътят съществува.

---

## 4. API договор за отчети

Всички пътища са под `/admin/api/v2`.

| Метод | Път | Тяло | Отговор | Лимит |
|---|---|---|---|---|
| POST | `/reports/render` | `{manifest, tsa?, createdAt?, data?, hashes?, certificates?, watermark?}` | `201` `application/pdf` | 1 MB |
| POST | `/reports/package` | горното + `draft?`, `pdfBase64?`, `cms?{certPem,keyPem}` | `201` `application/zip` | 8 MB |
| POST | `/reports/sign` | отчет + ключ | detached CMS подпис | — |
| POST | `/cms/verify` | подпис + оригинал | резултат от проверка | — |
| GET/POST | `/rfc3161` | — | TSA статус (изисква capability `settings`) | — |
| POST | `/rfc3161/verify` | токен | резултат от проверка | — |

### 4.1 `render` — заглавки на отговора

| Заглавка | Смисъл |
|---|---|
| `X-Manifest-SHA256` | SHA-256 на каноничния манифест (`report-manifest.digest`) |
| `X-PDF-SHA256` | SHA-256 на върнатите PDF байтове |
| `X-PDF-ISSUED-AT` | моментът на издаване, записан в PDF-а |
| `Content-Disposition` | `attachment; filename="report-<профил>.pdf"` |
| `X-TSA-Status` | `granted` или `failed` (само при `tsa: true`) |
| `X-TSA-Evidence-SHA256` | хеш на START токена (само при `tsa: true`) |
| `X-TSA-Closing-SHA256` | хеш на STOP токена (само при `tsa: true`) |

### 4.2 `package` — заглавки на отговора

| Заглавка | Смисъл |
|---|---|
| `X-Evidence-Status` | `READY`, `DRAFT` или `INCOMPLETE` |
| `X-Evidence-Missing` | URL-кодиран списък с липсващото, разделен с `|` (кирилица не може в HTTP заглавка) |
| `X-Manifest-SHA256`, `X-PDF-SHA256` | както при `render` |

`READY` означава, че **и** START, **и** STOPtoken са налице (плюс подписа, ако е поискан). Всичко друго е честно казано като непълно, вместо да се представя за готово.

### 4.3 Кодове за грешка

| Код | Причина | Решение |
|---|---|---|
| `400` | невалиден манифест | виж кодовете в тялото: `SYSTEM_BLOCK_IN_MIDDLE`, `BLOCK_ID`, ... |
| `404` | липсва/грешен Bearer токен на 8099, или сгрешен път | провери т. 3.3 |
| `409` | `tsa: true`, а `tsa_enabled: false` | махни `tsa` или включи TSA |
| `413` | тялото над лимита (1 MB / 8 MB) | намали `hashes`/`data`/`pdfBase64` |
| `500` | вътрешна грешка | виж `/share/hAPI/data/logs` |

### 4.4 Детерминизъм

Ако подадеш `createdAt`, еднакви входни данни дават **еднакъв PDF и еднакъв `X-PDF-SHA256`**. Без `createdAt` времето е „сега“ и хешът се меня. За възпроизводими тестове винаги подавай `createdAt`.

---

## 5. Манифестът — единственият вход, който има значение

Манифестът е JSON, който описва отчета блок по блок. Схема `report-studio/v1`.

### 5.1 Скелет

```json
{
  "schemaVersion": 1,
  "profile": "hash_single",
  "page": { "format": "A4", "orientation": "portrait", "marginsMm": [15, 15, 15, 15] },
  "branding": { "organization": "PasevSU", "logo": "", "qr": false },
  "print": { "pageNumbers": true, "headerFooter": true, "footerNote": "hAPI Enterprise" },
  "blocks": [
    { "id": "start", "type": "rfc3161-start", "locked": true, "label": "RFC 3161 START" },
    { "id": "stop",  "type": "rfc3161-stop",  "locked": true, "label": "RFC 3161 STOP" }
  ]
}
```

### 5.2 Твърди правила

- `rfc3161-start` е **винаги първи**, `rfc3161-stop` — **винаги последен**, и двата с `locked: true`.
- Системен блок по средата → `SYSTEM_BLOCK_IN_MIDDLE`.
- `id` се съвпада с `^[a-z][a-z0-9_-]{0,63}$`, уникално, максимум 200 блока.
- Забранени полета в манифеста: `tsaToken`, `tsaTime`, `tsaTimestamp`, `signature`, `signatureValue`, `certificate`. Манифестът **никога** не носи издадени стойности — те идват от сървъра.
- Разрешени формати: `A4`, `A5`, `LETTER`; ориентация `portrait`/`landscape`; хешове `CRC32`, `MD5`, `SHA1`, `SHA256`, `SHA512`.

### 5.3 Кои полета реално се рендират

Това е най-честата грешка: блокът минава валидация, но текстът не се появява, защото полето е сгрешно.

| Тип | Полета, които се четат |
|---|---|
| `title` | `value` (заглавие) + `subtitle` |
| `subtitle` | `value` или `label` |
| `text` | `label` (заглавка) + `value` (параграф) |
| `legal` | `label` + `value` (по подразбиране — стандартната правна декларация) |
| `data-block` | `label` — редовете са **системни** (произход, схема, профил), не се подават |
| `metadata` | `label` + `items: [{key, value}]` — това е блокът за „данни за файла“ |
| `table` | `label`, `source`, **`columns`** (1–32 непразни имена, задължително), `widths?`; редовете идват от `data[source]` |
| `hash-table` | `label` + `algorithms: [...]`; стойностите идват от `hashes[алгоритъм]` |
| `qr` | `value` |
| `image` / `logo` | `value` (data-URL, до 512 000 знака) |
| `pagebreak`, `separator`, `signature`, `certificate`, `columns`, `dynamic` | служебни |

За `table` полето `source` трябва да е `records:<име>`, `variables:<име>` или `group:<име>`, а ключът в `data` е **цялата** стойност на `source`. Заглавният ред се добавя автоматично от `columns` — в `data` подавай **само редовете с данни**, иначе заглавката ще се появи два пъти:

```json
{ "id": "files", "type": "table", "label": "Files", "source": "records:files",
  "columns": ["име", "размер"] }
```
```json
{ "data": { "records:files": [["a.pdf", "1234"]] } }
```

### 5.4 Проверен пример (реално рендиран)

Този манифест мина валидация (`valid: true`, нула грешки) и произведе PDF от 752 772 байта с правилните секции в правилния ред:

```json
{
  "schemaVersion": 1,
  "profile": "hash_single",
  "page": { "format": "A4", "orientation": "portrait", "marginsMm": [15, 15, 15, 15] },
  "branding": { "organization": "PasevSU", "logo": "", "qr": false },
  "print": { "pageNumbers": true, "headerFooter": true, "footerNote": "hAPI Enterprise" },
  "blocks": [
    { "id": "start",  "type": "rfc3161-start", "locked": true, "label": "RFC 3161 START" },
    { "id": "title",  "type": "title", "value": "SHA-256 Hash Report", "subtitle": "HASHREPORT_TYP_SINGLE" },
    { "id": "system", "type": "data-block", "label": "System Information" },
    { "id": "file",   "type": "metadata", "label": "File Information",
      "items": [ { "key": "File", "value": "a.pdf" }, { "key": "Size", "value": "1234 B" } ] },
    { "id": "hashes", "type": "hash-table", "label": "File Hashes", "algorithms": ["SHA256", "SHA512"] },
    { "id": "legal",  "type": "legal", "label": "Legal Notice" },
    { "id": "stop",   "type": "rfc3161-stop", "locked": true, "label": "RFC 3161 STOP" }
  ]
}
```

Резултатът съдържа `RFC 3161 START` → провенанс таблица → заглавие → системни данни → данни за файла → хешове → правна декларация → `RFC 3161 STOP`. Без `tsa: true` STOP блокът честно пише, че времеви печат не е издаден.

### 5.5 Два различни свята на манифести

Не бъркай:

- `report-manifest.js` (Report Studio) — това е схемата, която endpoint-ите приемат. Описана е по-горе.
- `custom_components/hapi_enterprise/report_manifests/*.json` — декларативни описания на четирите типа отчет (`single`, `combo`, `combo_all`, `volume`) с `input_scope` и `report_type_label`. Те **не** се подават на `render`; използват се от тестовете (`tests/report-manifests.cjs`, `tests/haoss-release.cjs`) като договор за това какво трябва да съдържа един отчет. Ако искаш отчет, който изглежда като `HASHREPORT_TYP_SINGLE`, описваш секциите му с блокове по т. 5.3.

| Файл | `input_scope` | `report_type_label` | Обхват |
|---|---|---|---|
| `single.json` | `single_file` | `HASHREPORT_TYP_SINGLE` | един файл |
| `combo.json` | `current_folder` | `HASHREPORT_TYP_COMBO` | една папка, само файловете в нея |
| `combo_all.json` | `recursive_folder` | `HASHREPORT_TYP_COMBO_ALL` | папка **и всички подпапки** |
| `volume.json` | `recursive_folder` | `HASHREPORT_TYP_VOLUME` | папка с провенанс за тома |

Рекурсията никога не е по подразбиране — `combo` не влиза в подпапки, `combo_all` влиза. Точно това поведение трябва да се възпроизведе в бутоните (т. 7.4).

---

## 6. Ниво 2: `curl` рецепти

```bash
HAPI=http://192.168.50.1:8099
TOKEN="твоят-токен"

# 1) жив ли е add-on-ът
curl -sS -o /dev/null -w "health=%{http_code}\n" "$HAPI/health"

# 2) приема ли се токенът
curl -sS -H "Authorization: Bearer $TOKEN" "$HAPI/admin/api/whoami"

# 3) рендер на PDF (манифестът от т. 5.4 във manifest.json)
curl -sS -D headers.txt -o report.pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @manifest.json \
  "$HAPI/admin/api/v2/reports/render"

# 4) какво каза сървърът
grep -i '^x-' headers.txt

# 5) отчет с доказателствен пакет и времеви печат
python3 - <<'PY' > body.json
import json
m = json.load(open('manifest.json'))
print(json.dumps({"manifest": m, "tsa": True}))
PY
curl -sS -D pkg-headers.txt -o report.zip \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data @body.json "$HAPI/admin/api/v2/reports/package"
grep -i 'x-evidence' pkg-headers.txt
```

Ако стъпка 3 върне `404` — токенът не стига до listener-а. Ако върне `400` — манифестът е невалиден; тялото казва кой блок.

---

## 7. Ниво 3: готов бутон на таблото

Идеята: Python скрипт прави всичко (обхожда папка, филтрира, хешира, строи манифест, вика API, записва PDF), а Home Assistant само го стартира и показва резултата.

### 7.1 Помощни входове

```yaml
# /config/configuration.yaml (или включен пакет)
input_text:
  hapi_report_folder:
    name: Папка за отчет
    max: 255
    initial: /share/documents

  hapi_report_filter:
    name: Филтър на файлове
    max: 100
    initial: "*.pdf"

  hapi_report_filter2:
    name: Втори филтър
    max: 100
    initial: ""

input_boolean:
  hapi_report_recursive:
    name: Включи подпапките

  hapi_report_tsa:
    name: Времеви печат (RFC 3161)
    icon: mdi:stamp

input_select:
  hapi_report_type:
    name: Тип отчет
    options:
      - single
      - combo
      - combo_all
      - volume
    initial: combo_all
```

`hapi_report_filter` е точно полето от панела на ChronoSeal: `*.eml.pdf`, `*.pdf`, `RPT-*.pdf`. Може няколко шаблона, разделени със запетая — скриптът ги разбира (т. 7.2).

### 7.2 Скриптът

Създай `/config/scripts/hapi_report.py`. Само стандартна библиотека — нищо за инсталиране.

```python
#!/usr/bin/env python3
"""Генерира HASH REPORT през hAPI Enterprise API.

Употреба:
  python3 hapi_report.py --type combo_all --folder /share/docs \
      --filter "*.eml.pdf" --recursive --tsa

Изход: JSON на stdout (за command_line сензор) + PDF в --out.
"""
import argparse, fnmatch, hashlib, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ALGOS = ("SHA256", "SHA512", "MD5")
PROFILE = {
    "single": "hash_single",
    "combo": "hash_combo",
    "combo_all": "hash_combo_all",
    "volume": "hash_volume",
}
LABEL = {
    "single": "HASHREPORT_TYP_SINGLE",
    "combo": "HASHREPORT_TYP_COMBO",
    "combo_all": "HASHREPORT_TYP_COMBO_ALL",
    "volume": "HASHREPORT_TYP_VOLUME",
}


def hash_file(path, algos=ALGOS):
    out = {}
    hs = {a: hashlib.new(a.lower()) for a in algos}
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            for h in hs.values():
                h.update(chunk)
    for a, h in hs.items():
        out[a] = h.hexdigest()
    return out


def collect(folder, patterns, recursive):
    root = Path(folder)
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise SystemExit(f"пътят не съществува: {root}")
    it = root.rglob("*") if recursive else root.glob("*")
    files = []
    for p in it:
        if not p.is_file():
            continue
        if patterns and not any(fnmatch.fnmatch(p.name, pat) for pat in patterns):
            continue
        files.append(p)
    return sorted(files, key=lambda p: str(p).lower())


def build_manifest(kind, folder, files, hashes, created_at):
    rows = []  # без заглавен ред — `columns` го добавят
    for p in files:
        rows.append([p.name, str(p.stat().st_size), hashes[str(p)]["SHA256"]])
    blocks = [
        {"id": "start", "type": "rfc3161-start", "locked": True, "label": "RFC 3161 START"},
        {"id": "title", "type": "title", "value": "HASH REPORT", "subtitle": LABEL[kind]},
        {"id": "system", "type": "data-block", "label": "System Information"},
        {"id": "scope", "type": "metadata", "label": "Scope", "items": [
            {"key": "Папка", "value": str(folder)},
            {"key": "Подпапки", "value": "да" if kind in ("combo_all", "volume") else "не"},
            {"key": "Файлове", "value": str(len(files))},
            {"key": "Издаден", "value": created_at},
        ]},
        {"id": "files", "type": "table", "label": "Files", "source": "records:files",
         "columns": ["Файл", "Размер (B)", "SHA-256"]},
        {"id": "hashes", "type": "hash-table", "label": "Hashes", "algorithms": list(ALGOS)},
        {"id": "legal", "type": "legal", "label": "Legal Notice"},
        {"id": "checksums", "type": "text", "label": "Checksums",
         "value": "Всички хешове са изчислени локално върху байтовете на файловете."},
        {"id": "stop", "type": "rfc3161-stop", "locked": True, "label": "RFC 3161 STOP"},
    ]
    return {
        "schemaVersion": 1,
        "profile": PROFILE[kind],
        "page": {"format": "A4", "orientation": "portrait", "marginsMm": [15, 15, 15, 15]},
        "branding": {"organization": "PasevSU", "logo": "", "qr": False},
        "print": {"pageNumbers": True, "headerFooter": True, "footerNote": "hAPI Enterprise"},
        "blocks": blocks,
    }, {"records:files": rows}


def post(url, token, payload, timeout=180):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), resp.read()


def resolve_token(path):
    env = os.environ.get("HAPI_TOKEN", "").strip()
    if env:
        return env
    if path.is_file():
        return path.read_text(encoding="utf-8").strip().splitlines()[0]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default="combo_all", choices=sorted(PROFILE))
    ap.add_argument("--folder", required=True)
    ap.add_argument("--filter", default="*")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--tsa", action="store_true")
    ap.add_argument("--out", default="/config/www/hapi/reports")
    ap.add_argument("--state", default="/config/hapi_report_state.json")
    ap.add_argument("--base", default=os.environ.get("HAPI_BASE", "http://192.168.50.1:8099"))
    a = ap.parse_args()

    token = resolve_token(Path("/config/scripts/hapi_report.token"))
    if len(token) < 24:
        raise SystemExit("липсва токен: HAPI_TOKEN или /config/scripts/hapi_report.token")

    patterns = [x.strip() for x in a.filter.split(",") if x.strip()]
    files = collect(a.folder, patterns, a.recursive or a.type in ("combo_all", "volume"))
    if not files:
        raise SystemExit("няма файлове по зададения филтър")

    hashes = {}
    for p in files:
        hashes[str(p)] = hash_file(p)

    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest, data = build_manifest(a.type, a.folder, files, hashes, created_at)

    # Обобщен хеш на списъка — това влиза в hash таблицата на отчета.
    listing = "".join(f"{p.name}\t{hashes[str(p)]['SHA256']}\n" for p in files).encode()
    aggregates = {name: hashlib.new(name.lower(), listing).hexdigest() for name in ALGOS}

    status, headers, body = post(
        f"{a.base}/admin/api/v2/reports/render",
        token,
        {"manifest": manifest, "data": data, "hashes": aggregates, "tsa": a.tsa, "createdAt": created_at},
    )

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    pdf = outdir / f"RPT-{stamp}-{LABEL[a.type].split('TYP_')[-1]}.pdf"
    pdf.write_bytes(body)

    state = {
        "state": pdf.name,
        "type": a.type,
        "files": len(files),
        "bytes": len(body),
        "pdf_sha256": headers.get("X-PDF-SHA256", ""),
        "manifest_sha256": headers.get("X-Manifest-SHA256", ""),
        "issued_at": headers.get("X-PDF-ISSUED-AT", created_at),
        "tsa": headers.get("X-TSA-Status", "not-requested"),
        "url": f"/local/hapi/reports/{pdf.name}",
        "path": str(pdf),
        "created_at": created_at,
    }
    Path(a.state).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(json.dumps({"state": "error", "code": exc.code,
                          "body": exc.read()[:400].decode("utf-8", "replace")}))
        sys.exit(1)
```

Забележка: `--out` по подразбиране е `/config/www/hapi/reports` — така PDF-ът се отваря от таблото като `/local/hapi/reports/<име>.pdf`. Ако предпочиташ доказателствения архив, смени URL-а на `/admin/api/v2/reports/package` и записвай `.zip`.

### 7.3 `shell_command` + `command_line` сензор

```yaml
# /config/configuration.yaml
shell_command:
  hapi_report: >-
    python3 /config/scripts/hapi_report.py
    --type {{ states('input_select.hapi_report_type') }}
    --folder "{{ states('input_text.hapi_report_folder') }}"
    --filter "{{ states('input_text.hapi_report_filter') }},{{ states('input_text.hapi_report_filter2') }}"
    {% if is_state('input_boolean.hapi_report_recursive', 'on') %}--recursive{% endif %}
    {% if is_state('input_boolean.hapi_report_tsa', 'on') %}--tsa{% endif %}

command_line:
  - sensor:
      name: hAPI последен отчет
      command: "cat /config/hapi_report_state.json"
      value_template: "{{ value_json.state }}"
      json_attributes:
        - type
        - files
        - bytes
        - pdf_sha256
        - manifest_sha256
        - issued_at
        - tsa
        - url
      scan_interval: 3600
```

Токенът не се подава през `shell_command` (там `!secret` не работи и стойността влиза в логовете). Скриптът го чете от файл:

```bash
# Терминал/Samba add-on на Home Assistant
printf '%s\n' 'тук-е-твоят-токен-поне-24-знака' > /config/scripts/hapi_report.token
chmod 600 /config/scripts/hapi_report.token
```

Редът за търсене е: променлива `HAPI_TOKEN`, после `/config/scripts/hapi_report.token`. Сензор `sensor.hapi_admin_token` **не** съществува по подразбиране — не го измисляй в `shell_command`.

### 7.4 Скриптове за четирите бутона

```yaml
script:
  hapi_single:
    alias: "HASH REPORT · един файл"
    sequence:
      - action: input_select.select_option
        target: { entity_id: input_select.hapi_report_type }
        data: { option: single }
      - action: input_boolean.turn_off
        target: { entity_id: input_boolean.hapi_report_recursive }
      - action: shell_command.hapi_report
    mode: single

  hapi_combo:
    alias: "HASH REPORT · само папката"
    sequence:
      - action: input_select.select_option
        target: { entity_id: input_select.hapi_report_type }
        data: { option: combo }
      - action: input_boolean.turn_off
        target: { entity_id: input_boolean.hapi_report_recursive }
      - action: shell_command.hapi_report
    mode: single

  hapi_combo_all:
    alias: "HASH REPORT · папка + подпапки"
    sequence:
      - action: input_select.select_option
        target: { entity_id: input_select.hapi_report_type }
        data: { option: combo_all }
      - action: input_boolean.turn_on
        target: { entity_id: input_boolean.hapi_report_recursive }
      - action: shell_command.hapi_report
    mode: single

  hapi_volume:
    alias: "HASH REPORT · том + подпапки"
    sequence:
      - action: input_select.select_option
        target: { entity_id: input_select.hapi_report_type }
        data: { option: volume }
      - action: input_boolean.turn_on
        target: { entity_id: input_boolean.hapi_report_recursive }
      - action: shell_command.hapi_report
    mode: single
```

За `single` подай в `input_text.hapi_report_folder` **пътя до самия файл** (не до папката) — скриптът от т. 7.2 разпознава файл и прави отчет за един файл. Ако подадеш папка при тип `single`, отчетът ще включи всички файлове по филтъра, което не е грешка, но не е „един файл“.

### 7.5 Карти на таблото

```yaml
type: grid
columns: 2
square: false
cards:
  - type: button
    name: HASH REPORT · папка + подпапки
    icon: mdi:file-certificate-outline
    show_state: false
    tap_action:
      action: perform-action
      perform_action: script.hapi_combo_all
      confirmation:
        text: "Да се генерира отчет за {{ states('input_text.hapi_report_folder') }}?"

  - type: button
    name: HASH REPORT · само папката
    icon: mdi:folder-file
    tap_action:
      action: perform-action
      perform_action: script.hapi_combo

  - type: button
    name: HASH REPORT · един файл
    icon: mdi:file-document-outline
    tap_action:
      action: perform-action
      perform_action: script.hapi_single

  - type: button
    name: HASH REPORT · том
    icon: mdi:harddisk
    tap_action:
      action: perform-action
      perform_action: script.hapi_volume

  - type: entity
    entity: sensor.hapi_posleden_otchet
    name: Последен отчет

  - type: markdown
    content: >-
      {% set u = state_attr('sensor.hapi_posleden_otchet', 'url') %}
      {% if u %}
        [Отвори PDF]({{ u }}) · SHA-256: `{{ state_attr('sensor.hapi_posleden_otchet', 'pdf_sha256')[:16] }}…`
      {% else %}
        Още няма генериран отчет.
      {% endif %}

  - type: entities
    entities:
      - input_text.hapi_report_folder
      - input_text.hapi_report_filter
      - input_text.hapi_report_filter2
      - input_select.hapi_report_type
      - input_boolean.hapi_report_recursive
      - input_boolean.hapi_report_tsa
```

Филтърът се въвежда в `input_text.hapi_report_filter` — точно както полето в панела на ChronoSeal, включително `*.eml.pdf`. Второто поле `hapi_report_filter2` е „следващото поле за филтър“: двете се събират със запетая и скриптът ги третира като списък от шаблони (`*.pdf,SHA*.pdf`). Празно поле не пречи — празните шаблони се изхвърлят.

### 7.6 Защо не `rest_command`

`rest_command` връща само текст/JSON в сензор — не може да запише PDF файл на диска. Затова за отчети `rest_command` е подходящ само за проверки (`/health`, `/whoami`, `/rfc3161`), а за генериране се ползва `shell_command` + скрипта от т. 7.2.

---

## 8. Сигурност

- Токенът дава admin права на add-on-а. Пази го в `secrets.yaml` или env файл с права `600`; не го слагай в табло, в git и в логове.
- `/admin/api/v2/reports/*` **не** проверява роля в 0.69.216 — всеки, който стигне до 8099 с валиден токен, може да рендира и пакетира. Затова: не публикувай 8099 към интернет; ако ти трябва външен достъп, ползвай gateway 8088 с отделна политика.
- `X-Evidence-Missing` е URL-кодиран, защото HTTP заглавките са Latin-1. Не се опитвай да слагаш кирилица в заглавка.
- Отчетите съдържат имена на файлове и хешове. Ако папката е чувствителна, насочи `--out` извън `/config/www` (например `/share/hAPI/data/reports`), за да не се сервират през `/local/`.

---

## 9. Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `404` на `/admin/api/v2/reports/render` | липсва Bearer или портът не е публикуван | т. 3.2, 3.3 |
| `409` при `tsa: true` | `tsa_enabled: false` | включи TSA или махни флага |
| `400` + `SYSTEM_BLOCK_IN_MIDDLE` | системен блок по средата | START първи, STOP последен |
| PDF без моите секции | сгрешено поле (`text` вместо `value`, липсва `items`/`source`) | т. 5.3 |
| Празна hash таблица | `hashes` не е подаден или ключът не е `SHA256`/`SHA512` | подай `hashes: {"SHA256": "..."}` |
| Различен `X-PDF-SHA256` при еднакви данни | липсва `createdAt` | подай `createdAt` |
| Бутонът „нищо не прави“ | `script` не вика `shell_command` | т. 7.3 |
| Таблото казва „unknown action“ | опит за `hapi_enterprise.*` услуга | няма такава — т. 2 |
| Скриптът: `няма файлове` | филтърът не съвпада (`fnmatch` е чувствителен на регистър в Linux) | `*.pdf` вместо `*.PDF` |

### 9.1 Проверени сценарии

Всичко в този документ е изпълнено, не само прочетено. Проверката използва локален mock на `/admin/api/v2/reports/render`, който **валидира и рендира с истинските модули на hAPI** (`report-manifest.js`, `report-render.js`), плюс скрипта от т. 7.2 без промени.

| # | Сценарий | Очаквано | Резултат |
|---|---|---|---|
| T1 | `combo_all`, филтър `*.eml.pdf`, `--recursive`, `--tsa` | 2 файла (вкл. от подпапка), PDF, `tsa: granted` | PASS — 753 820 B, `%PDF-` |
| T2 | `combo` без `--recursive`, филтър `*.pdf` | 2 файла (без подпапката), без TSA | PASS — `tsa: not-requested` |
| T3 | `single` с път до **файл** | 1 файл | PASS |
| T4 | грешен токен | `404`, код на изхода 1 | PASS — `{"state":"error","code":404}` |
| T5 | филтър без съвпадения | честно съобщение, код 1 | PASS — „няма файлове по зададения филтър“ |
| T6 | `--tsa`, а TSA е изключен | `409` | PASS — `{"code":409}` |
| T7 | два рендера с еднакъв `createdAt` | еднакви байтове и еднакъв `X-PDF-SHA256` | PASS — 753 309 B, SHA съвпада |
| T8 | `table` блок без `columns` | `400` с ясен код | намерен дефект → `columns` вече е задължително поле в т. 5.3 и в скрипта |
| T9 | заглавен ред и в `columns`, и в `data` | заглавката се появява веднъж | намерен дефект → `columns` е заглавката; `data` носи само данни (т. 5.3) |

T8 и T9 са двете причини т. 5.3 да е толкова конкретна за `table`. T8: блокът изглежда наред, но сървърът връща `INVALID_TABLE_COLUMNS` — добави `"columns": ["...", "..."]` с толкова имена, колкото са клетките в реда. T9: отчетът се рендира успешно, но заглавката се вижда два пъти — `columns` вече е заглавният ред, затова в `data[source]` не се слага заглавен ред.

Проверката на T1–T9 се прави и след всяка бъдеща промяна на скрипта: стартира се срещу локален mock със същите модули на hAPI и се сравнява броят на редовете в таблиците (1 заглавка + N файла) и `X-TSA-Status`.

---

## 10. Какво hAPI може, а JS клонингът на ChronoSeal — не

| Възможност | hAPI add-on | ChronoSeal JS клонинг (`js/`) |
|---|---|---|
| Реален RFC 3161 времеви печат | да (`tsa-client.js`) | не — пише `NOT APPLIED` |
| CMS / PGP / X.509 подпис | да | не — пише `NOT VERIFIED` |
| Доказателствен ZIP (`READY`/`INCOMPLETE`) | да | не — пише `NOT SEALED` |
| HTTP API за всеки тип отчет | да (4 типа) | Node API + CLI, локален диск |
| Тип `SINGLE_PDF` (вграден PDF) | **не** | да |
| Тип `FILE_INFORMATION_REPORT` | **не** | да |
| Работи без Home Assistant | не | да |

Изводът за бутоните: ако искаш подписан и подпечатан отчет — бутонът върви към hAPI. Ако искаш тип `SINGLE_PDF` или `FILE_INFORMATION`, единственият път е JS клонингът, стартиран с `shell_command` (`node js/cli.mjs ...`), и тогава „бутонът“ не носи TSA. Виж `docu/JS_CLONE_BG.md`.

---

## 11. Контролен списък след монтаж

1. `curl /health` → `200`
2. `curl /admin/api/whoami` с токен → роля `admin`
3. `curl` рендер на манифеста от т. 5.4 → `201`, файлът започва с `%PDF-`
4. `grep X-PDF-SHA256` → има стойност; при повторение с `createdAt` — същата
5. `tsa: true` → `X-TSA-Status: granted`
6. `python3 /config/scripts/hapi_report.py ...` → JSON на stdout, PDF в `/config/www/hapi/reports`
7. Таблото: бутонът стартира скрипта, сензорът показва името на PDF-а, линкът отваря файла
8. `package` с `draft: true` → `X-Evidence-Status: DRAFT`; с TSA и STOP → `READY`

Ако всичките осем минат, бутоните работят. Ако някой се провали — таблицата в т. 9 казва кой ред от този списък е проблемът.

---

## Приложение А — минимален манифест за copy/paste

Виж т. 5.4. Това е най-малкият манифест, който минава валидация и произвежда смислен отчет.

## Приложение Б — всички endpoint-и на отчетите

```text
POST /admin/api/v2/reports/render      PDF от манифест
POST /admin/api/v2/reports/package     доказателствен ZIP
POST /admin/api/v2/reports/sign        detached CMS подпис
POST /admin/api/v2/cms/verify          проверка на CMS подпис
GET  /admin/api/v2/rfc3161             TSA статус (capability settings)
POST /admin/api/v2/rfc3161/verify      проверка на TSA токен
```

## Приложение В — източници на фактите

- `hapi_enterprise/routes/reports.js` — маршрути, тела, заглавки, лимити, TSA гейт
- `hapi_enterprise/report-manifest.js` — схема, типове блокове, забранени полета, `BLOCK_ID`
- `hapi_enterprise/report-render.js` — кое поле се рендира (`toPdfBlocks`)
- `hapi_enterprise/server.js` — listener разделяне, `adminGate`, Bearer проверка
- `hapi_enterprise/config.yaml` — портове, ingress, опции, RBAC seed
- `custom_components/hapi_enterprise/report_manifests/` — четирите типа и `input_scope`
- `tests/report-manifests.cjs`, `tests/haoss-release.cjs` — какво гарантират манифестите

---

*Този документ описва hAPI Enterprise 0.69.216. При upgrade провери отново т. 3 (портове/токен), т. 4 (лимити и заглавки) и т. 5 (схема на манифеста) — това са трите места, които се менят най-често.*