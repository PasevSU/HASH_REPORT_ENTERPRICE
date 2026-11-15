"""Central GUI localisation (English default, Deutsch, Български).

Every Tk window is translated by one mechanism: text handed to widgets, window
titles, menus, message boxes and file dialogs is looked up in CATALOG. A text is
recognised in ANY of the three languages, so switching language at runtime
re-translates existing widgets without remembering their original wording.
Report PDFs, logs and engine output are intentionally not touched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LANGUAGES = {"en": "English", "de": "Deutsch", "bg": "Български"}
DEFAULT_LANGUAGE = "en"
_SETTINGS = Path(__file__).resolve().parent.parent / "config" / "ui.json"

# (English, Deutsch, Български). {name} marks a variable part.
CATALOG = [
    # ---- main window / navigation -------------------------------------
    ("ChronoSeal | Evidence Workspace", "ChronoSeal | Beweis-Arbeitsbereich", "ChronoSeal | Работна среда за доказателства"),
    ("ChronoSeal | Evidence & Timestamp Workspace", "ChronoSeal | Beweis- und Zeitstempel-Arbeitsbereich", "ChronoSeal | Работна среда за доказателства и времеви печати"),
    ("EVIDENCE OPERATIONS WORKSPACE", "ARBEITSBEREICH FÜR BEWEISSICHERUNG", "РАБОТНА СРЕДА ЗА ДОКАЗАТЕЛСТВА"),
    ("WORKSPACE", "ARBEITSBEREICH", "РАБОТНА ОБЛАСТ"),
    ("Report & TSA", "Bericht & TSA", "Отчет и TSA"),
    ("Generate, seal and verify", "Erzeugen, versiegeln und prüfen", "Генериране, запечатване и проверка"),
    ("Automation", "Automatisierung", "Автоматизация"),
    ("Plan recurring reports", "Wiederkehrende Berichte planen", "Планиране на повтарящи се отчети"),
    ("Automatic Reports", "Automatische Berichte", "Автоматични отчети"),
    ("Settings & Trust", "Einstellungen & Vertrauen", "Настройки и доверие"),
    ("Tools and TSA profiles", "Werkzeuge und TSA-Profile", "Инструменти и TSA профили"),
    ("Diagnostics", "Diagnose", "Диагностика"),
    ("Preflight and evidence logs", "Vorabprüfung und Beweisprotokolle", "Предварителна проверка и дневници"),
    ("Diagnostics & Logs", "Diagnose & Protokolle", "Диагностика и дневници"),
    ("Evidence-first workflow\nCtrl+1–4  ·  Navigate", "Beweis-zuerst-Arbeitsablauf\nStrg+1–4  ·  Navigation", "Работен процес с приоритет на доказателствата\nCtrl+1–4  ·  Навигация"),
    ("Language", "Sprache", "Език"),
    ("Workspace ready", "Arbeitsbereich bereit", "Работната среда е готова"),
    ("Created & licensed by Home Assistant Projects · PasevSU DEV", "Erstellt & lizenziert von Home Assistant Projects · PasevSU DEV", "Създадено и лицензирано от Home Assistant Projects · PasevSU DEV"),
    ("Part of the NO TRUST Cybersecurity volunteer campaign", "Teil der ehrenamtlichen Cybersicherheitskampagne NO TRUST", "Част от доброволческата кампания за киберсигурност NO TRUST"),
    # ---- run page -------------------------------------------------------
    ("Evidence pipeline", "Beweis-Pipeline", "Конвейер за доказателства"),
    ("Create and verify a report", "Bericht erstellen und prüfen", "Създаване и проверка на отчет"),
    ("Select a file or folder. ChronoSeal generates the report, applies configured timestamps and preserves verification evidence.",
     "Wählen Sie eine Datei oder einen Ordner. ChronoSeal erzeugt den Bericht, setzt die konfigurierten Zeitstempel und sichert die Prüfnachweise.",
     "Изберете файл или папка. ChronoSeal генерира отчета, поставя конфигурираните времеви печати и запазва доказателствата от проверката."),
    ("1  ·  Input source", "1  ·  Eingabequelle", "1  ·  Входен източник"),
    ("2  ·  Output", "2  ·  Ausgabe", "2  ·  Изход"),
    ("3  ·  Run and monitor", "3  ·  Ausführen und überwachen", "3  ·  Изпълнение и наблюдение"),
    ("Choose file", "Datei wählen", "Избор на файл"),
    ("Choose folder", "Ordner wählen", "Избор на папка"),
    ("Browse", "Durchsuchen", "Преглед"),
    ("Browse…", "Durchsuchen…", "Преглед…"),
    ("File…", "Datei…", "Файл…"),
    ("Folder…", "Ordner…", "Папка…"),
    ("Report type is detected from the selected input.", "Der Berichtstyp wird aus der Auswahl erkannt.", "Видът отчет се определя от избрания вход."),
    ("Include subfolders", "Unterordner einbeziehen", "Включи подпапките"),
    ("Recursive (folders only)", "Rekursiv (nur Ordner)", "Рекурсивно (само папки)"),
    ("Save report and evidence in a different folder", "Bericht und Nachweise in einem anderen Ordner speichern", "Запази отчета и доказателствата в друга папка"),
    ("Save in another folder (default: working folder)", "In anderem Ordner speichern (Standard: Arbeitsordner)", "Запази в друга папка (по подразбиране: работната)"),
    ("Generate report  ·  Timestamp  ·  Verify", "Bericht erzeugen  ·  Zeitstempel  ·  Prüfen", "Генерирай отчет  ·  Времеви печат  ·  Провери"),
    ("ONE BUTTON — REPORT → RFC3161 → FINAL VERIFY → EVIDENCE", "EIN KLICK — BERICHT → RFC3161 → ENDPRÜFUNG → NACHWEIS", "ЕДИН БУТОН — ОТЧЕТ → RFC3161 → КРАЙНА ПРОВЕРКА → ДОКАЗАТЕЛСТВА"),
    ("Cancel", "Abbrechen", "Отказ"),
    ("Stop / Cancel", "Stopp / Abbrechen", "Спри / Отказ"),
    ("LIVE RUN STATUS", "LIVE-STATUS DER AUSFÜHRUNG", "СЪСТОЯНИЕ НА ИЗПЪЛНЕНИЕТО НА ЖИВО"),
    ("Waiting to start  ·  0%", "Wartet auf Start  ·  0%", "Изчаква старт  ·  0%"),
    ("Execution log", "Ausführungsprotokoll", "Дневник на изпълнението"),
    ("Copy selected", "Auswahl kopieren", "Копирай избраното"),
    ("Copy all", "Alles kopieren", "Копирай всичко"),
    ("Copy all log", "Gesamtes Protokoll kopieren", "Копирай целия дневник"),
    ("Close", "Schließen", "Затвори"),
    ("Input source, folder, or already generated PDF", "Eingabequelle, Ordner oder bereits erzeugtes PDF", "Входен източник, папка или вече генериран PDF"),
    ("Report type: automatic (File → SINGLE / Folder → COMBO)", "Berichtstyp: automatisch (Datei → SINGLE / Ordner → COMBO)", "Вид отчет: автоматичен (Файл → SINGLE / Папка → COMBO)"),
    ("Report type: SINGLE (file selected)", "Berichtstyp: SINGLE (Datei gewählt)", "Вид отчет: SINGLE (избран файл)"),
    ("Report type: COMBO (folder selected)", "Berichtstyp: COMBO (Ordner gewählt)", "Вид отчет: COMBO (избрана папка)"),
    ("Ready", "Bereit", "Готов"),
    ("Startup check…", "Startprüfung…", "Стартова проверка…"),
    ("SETUP REQUIRED", "EINRICHTUNG ERFORDERLICH", "НЕОБХОДИМА Е НАСТРОЙКА"),
    ("STARTUP FAILED", "START FEHLGESCHLAGEN", "НЕУСПЕШЕН СТАРТ"),
    ("Ready — startup qualification PASS", "Bereit — Startqualifizierung bestanden", "Готов — стартовата квалификация е успешна"),
    ("Cancellation requested…", "Abbruch angefordert…", "Заявено е прекратяване…"),
    ("CANCELLED", "ABGEBROCHEN", "ПРЕКРАТЕНО"),
    ("BLOCKED", "BLOCKIERT", "БЛОКИРАНО"),
    ("PASS", "BESTANDEN", "ПРОЙДЕНО"),
    ("{n}% — {s}", "{n}% — {s}", "{n}% — {s}"),
    # ---- settings page --------------------------------------------------
    ("Configuration", "Konfiguration", "Конфигурация"),
    ("Manage the local runtime, report generator and timestamp provider trust.", "Lokale Laufzeit, Berichtsgenerator und Vertrauen in Zeitstempeldienste verwalten.", "Управление на локалната среда, генератора на отчети и доверието към доставчиците на времеви печати."),
    ("Windows integration, report archive and independent TSA trust", "Windows-Integration, Berichtsarchiv und unabhängiges TSA-Vertrauen", "Интеграция с Windows, архив на отчетите и независимо доверие към TSA"),
    ("Archive each sealed report, manifest, log and evidence in a numbered folder and SQLite database", "Jeden versiegelten Bericht samt Manifest, Protokoll und Nachweisen in nummeriertem Ordner und SQLite-Datenbank archivieren", "Архивирай всеки запечатан отчет, манифест, дневник и доказателства в номерирана папка и SQLite база данни"),
    ("Report archive folder", "Berichtsarchiv-Ordner", "Папка на архива на отчетите"),
    ("SQLite archive database", "SQLite-Archivdatenbank", "SQLite база данни на архива"),
    ("Hash generator package", "Hash-Generator-Paket", "Пакет на хеш генератора"),
    ("Node.js / node.exe", "Node.js / node.exe", "Node.js / node.exe"),
    ("OpenSSL / openssl.exe", "OpenSSL / openssl.exe", "OpenSSL / openssl.exe"),
    ("START provider preset", "START-Anbieterprofil", "START профил на доставчик"),
    ("STOP provider preset", "STOP-Anbieterprofil", "STOP профил на доставчик"),
    ("START TSA URL", "START-TSA-URL", "START TSA адрес"),
    ("STOP TSA URL", "STOP-TSA-URL", "STOP TSA адрес"),
    ("START trust cert(s)", "START-Vertrauenszertifikat(e)", "START сертификат(и) за доверие"),
    ("STOP trust cert(s)", "STOP-Vertrauenszertifikat(e)", "STOP сертификат(и) за доверие"),
    ("Apply", "Anwenden", "Приложи"),
    ("Auto-detect Windows tools", "Windows-Werkzeuge automatisch erkennen", "Автоматично откриване на инструменти"),
    ("Save settings", "Einstellungen speichern", "Запази настройките"),
    ("Run preflight", "Vorabprüfung ausführen", "Стартирай предварителна проверка"),
    ("Bootstrap TSA trust", "TSA-Vertrauen initialisieren", "Инициализирай доверието към TSA"),
    ("Trust certificates must be approved certificates/chains for the external TSA. ChronoSeal does not generate production TSA certificates.",
     "Vertrauenszertifikate müssen freigegebene Zertifikate/Ketten der externen TSA sein. ChronoSeal erzeugt keine produktiven TSA-Zertifikate.",
     "Сертификатите за доверие трябва да са одобрени сертификати/вериги на външната TSA. ChronoSeal не генерира производствени TSA сертификати."),
    ("Executable", "Ausführbare Datei", "Изпълним файл"),
    ("Certificates", "Zertifikate", "Сертификати"),
    ("SQLite database", "SQLite-Datenbank", "SQLite база данни"),
    ("All files", "Alle Dateien", "Всички файлове"),
    # ---- diagnostics ----------------------------------------------------
    ("Operational assurance", "Betriebssicherheit", "Оперативна сигурност"),
    ("Diagnostics & evidence", "Diagnose & Nachweise", "Диагностика и доказателства"),
    ("Run a preflight, inspect status and open the retained evidence package.", "Vorabprüfung ausführen, Status prüfen und das gesicherte Nachweispaket öffnen.", "Стартирайте предварителна проверка, прегледайте състоянието и отворете запазения пакет с доказателства."),
    ("Diagnostics and complete log package", "Diagnose und vollständiges Protokollpaket", "Диагностика и пълен пакет с дневници"),
    ("Refresh diagnostics", "Diagnose aktualisieren", "Обнови диагностиката"),
    ("Open latest log folder", "Neuesten Protokollordner öffnen", "Отвори последната папка с дневници"),
    ("Open evidence folder", "Nachweisordner öffnen", "Отвори папката с доказателства"),
    # ---- context menu / dialogs / messages ------------------------------
    ("Cut", "Ausschneiden", "Изрежи"),
    ("Copy", "Kopieren", "Копирай"),
    ("Paste", "Einfügen", "Постави"),
    ("Select all", "Alles auswählen", "Избери всичко"),
    ("ChronoSeal — Setup required", "ChronoSeal — Einrichtung erforderlich", "ChronoSeal — Необходима е настройка"),
    ("Startup qualification BLOCKED:", "Startqualifizierung BLOCKIERT:", "Стартовата квалификация е БЛОКИРАНА:"),
    ("Report:", "Bericht:", "Отчет:"),
    ("Startup repair completed automatically:", "Startreparatur automatisch abgeschlossen:", "Стартовата поправка е завършена автоматично:"),
    ("ChronoSeal is ready.", "ChronoSeal ist bereit.", "ChronoSeal е готов."),
    ("Startup self-check failed:", "Selbstprüfung beim Start fehlgeschlagen:", "Самопроверката при старт е неуспешна:"),
    ("ChronoSeal Provider Profile", "ChronoSeal-Anbieterprofil", "ChronoSeal профил на доставчик"),
    ("Windows tool detection completed. Review paths and Save settings.", "Werkzeugerkennung abgeschlossen. Pfade prüfen und Einstellungen speichern.", "Откриването на инструменти приключи. Прегледайте пътищата и запазете настройките."),
    ("Settings saved.", "Einstellungen gespeichert.", "Настройките са запазени."),
    ("OpenSSL is required for TSA trust bootstrap.", "OpenSSL ist für die TSA-Vertrauensinitialisierung erforderlich.", "За инициализиране на доверието към TSA е необходим OpenSSL."),
    ("TSA trust bootstrap PASS. Certificate chains were validated and saved locally.", "TSA-Vertrauensinitialisierung BESTANDEN. Zertifikatsketten wurden geprüft und lokal gespeichert.", "Инициализирането на доверието към TSA е успешно. Веригите от сертификати са проверени и запазени локално."),
    ("TSA trust bootstrap BLOCKED:", "TSA-Vertrauensinitialisierung BLOCKIERT:", "Инициализирането на доверието към TSA е БЛОКИРАНО:"),
    ("Select input on the Run tab first.", "Wählen Sie zuerst die Eingabe auf der Registerkarte „Ausführen“.", "Първо изберете вход в раздела за изпълнение."),
    ("ChronoSeal Preflight", "ChronoSeal-Vorabprüfung", "ChronoSeal предварителна проверка"),
    ("Startup qualification has not passed. Resolve Setup/Diagnostics blockers first.", "Die Startqualifizierung wurde nicht bestanden. Beheben Sie zuerst die Blocker in Einrichtung/Diagnose.", "Стартовата квалификация не е преминала. Първо отстранете блокерите в настройките/диагностиката."),
    ("Select input first.", "Wählen Sie zuerst eine Eingabe.", "Първо изберете вход."),
    ("Select an existing output folder.", "Wählen Sie einen vorhandenen Ausgabeordner.", "Изберете съществуваща изходна папка."),
    ("ChronoSeal — ERLAEUTERUNG", "ChronoSeal — ERLÄUTERUNG", "ChronoSeal — ERLAEUTERUNG"),
    ("Include ERLAEUTERUNG.pdf as pages in the main report?", "ERLAEUTERUNG.pdf als Seiten in den Hauptbericht aufnehmen?", "Да се включи ли ERLAEUTERUNG.pdf като страници в основния отчет?"),
    ("ChronoSeal — PDF embedding", "ChronoSeal — PDF-Einbettung", "ChronoSeal — PDF вграждане"),
    ("Switch to the separate PDF mode for embedding the pages?\n\nYES: SINGLE report + ERLAEUTERUNG (if selected) + PDF pages and original as attachment.\nNO: standard SINGLE hash report.",
     "Zum separaten PDF-Modus für die Seiteneinbettung wechseln?\n\nJA: SINGLE-Bericht + ERLAEUTERUNG (falls gewählt) + PDF-Seiten und Original als Anhang.\nNEIN: Standard-SINGLE-Hashbericht.",
     "Да се премине ли към отделния PDF режим за вграждане на страниците?\n\nДА: SINGLE отчет + ERLAEUTERUNG (ако е избран) + PDF страници и оригинал като приложение.\nНЕ: стандартен SINGLE хеш отчет."),
    ("Full log:", "Vollständiges Protokoll:", "Пълен дневник:"),
    ("Application closed", "Anwendung geschlossen", "Приложението е затворено"),
    # ---- automation panel ----------------------------------------------
    ("Ready for {mode}", "Bereit für {mode}", "Готов за {mode}"),
    ("Self-contained functional block · planning, execution, TSA and reporting", "Eigenständiger Funktionsblock · Planung, Ausführung, TSA und Berichtswesen", "Самостоятелен функционален блок · планиране, изпълнение, TSA и отчетност"),
    ("FILES", "DATEIEN", "ФАЙЛОВЕ"),
    ("VOLUME", "UMFANG", "ОБЕМ"),
    ("EXECUTION", "AUSFÜHRUNG", "ИЗПЪЛНЕНИЕ"),
    ("{n} files loaded", "{n} Dateien geladen", "{n} заредени файла"),
    ("{size} MB total size", "{size} MB Gesamtgröße", "{size} MB общ размер"),
    ("0 B total size", "0 B Gesamtgröße", "0 B общ размер"),
    ("{n} jobs processed", "{n} Aufträge verarbeitet", "{n} обработени задачи"),
    ("{n} / {t} jobs", "{n} / {t} Aufträge", "{n} / {t} задачи"),
    ("Directory:", "Verzeichnis:", "Директория:"),
    ("Select…", "Auswählen…", "Избери…"),
    ("Combined report", "Kombinierter Bericht", "Комбиниран отчет"),
    ("Individual report", "Einzelbericht", "Индивидуален отчет"),
    ("Combined and individual report", "Kombinierter und Einzelbericht", "Комбиниран и индивидуален отчет"),
    ("1. Report type:", "1. Berichtstyp:", "1. Вид на отчета:"),
    ("2. Automation:", "2. Automatisierung:", "2. Автоматизация:"),
    ("One combined report for all files in the selected folder", "Ein gemeinsamer Bericht für alle Dateien im gewählten Ordner", "Един общ отчет за всички файлове в избраната папка"),
    ("One combined report for the folder and all subfolders", "Ein gemeinsamer Bericht für den Ordner und alle Unterordner", "Един общ отчет за папката и всички подпапки"),
    ("One combined report for selected files only", "Ein gemeinsamer Bericht nur für ausgewählte Dateien", "Един общ отчет само за избрани файлове"),
    ("A separate report for each file in the selected folder", "Ein eigener Bericht für jede Datei im gewählten Ordner", "Отделен отчет за всеки файл в избраната папка"),
    ("A separate report for the selected files only", "Ein eigener Bericht nur für die ausgewählten Dateien", "Отделен отчет само за избраните файлове"),
    ("Separate reports and one combined report for the folder", "Einzelberichte und ein gemeinsamer Bericht für den Ordner", "Отделни отчети и един общ отчет за папката"),
    ("Separate reports and one combined report for selected files only", "Einzelberichte und ein gemeinsamer Bericht nur für ausgewählte Dateien", "Отделни отчети и един общ отчет само за избрани файлове"),
    ("A separate report with TSA for each selected file. Other files are skipped.", "Ein eigener Bericht mit TSA für jede markierte Datei. Andere Dateien werden übersprungen.", "Отделен отчет с TSA за всеки маркиран файл. Другите файлове се пропускат."),
    ("A separate report with TSA for each file in the current folder.", "Ein eigener Bericht mit TSA für jede Datei im aktuellen Ordner.", "Отделен отчет с TSA за всеки файл от текущата папка."),
    ("One combined report with TSA for the current folder.", "Ein kombinierter Bericht mit TSA für den aktuellen Ordner.", "Един комбиниран отчет с TSA за текущата папка."),
    ("One combined report with TSA for the folder and subfolders.", "Ein kombinierter Bericht mit TSA für den Ordner und die Unterordner.", "Един комбиниран отчет с TSA за папката и подпапките."),
    ("One combined report for the selected files only; a temporary working folder with copies is used for execution.", "Ein kombinierter Bericht nur für die markierten Dateien; zur Ausführung wird ein temporärer Arbeitsordner mit Kopien verwendet.", "Един комбиниран отчет само за маркираните файлове; за изпълнението се използва временна работна папка с копия."),
    ("Separate reports for the files and one combined report for the folder.", "Einzelberichte für die Dateien und ein kombinierter Bericht für den Ordner.", "Отделни отчети за файловете и един комбиниран отчет за папката."),
    ("Separate reports and one combined report for the selected files only.", "Einzelberichte und ein kombinierter Bericht nur für die markierten Dateien.", "Отделни отчети и един комбиниран отчет само за маркираните файлове."),
    ("File selection (Ctrl/Shift)", "Dateiauswahl (Strg/Umschalt)", "Избор на файлове (Ctrl/Shift)"),
    ("Add files…", "Dateien hinzufügen…", "Добави файлове…"),
    ("Remove selected", "Markierte entfernen", "Премахни маркираните"),
    ("Clear list", "Liste leeren", "Изчисти списъка"),
    ("Selected mode settings", "Einstellungen des gewählten Modus", "Настройки на избрания режим"),
    ("Add the specific files with the “Add files…” button. The panel shows only the loaded files.", "Fügen Sie die Dateien über „Dateien hinzufügen…“ hinzu. Das Panel zeigt nur geladene Dateien.", "Добавете конкретните файлове с бутона „Добави файлове…“. Панелът показва само заредените файлове."),
    ("Processing uses the specified directory.", "Die Verarbeitung verwendet das angegebene Verzeichnis.", "Обработката използва зададената директория."),
    ("▶ Start", "▶ Start", "▶ Старт"),
    ("Show plan", "Plan anzeigen", "Покажи плана"),
    ("■ Stop", "■ Stopp", "■ Спри"),
    ("Real-time monitoring", "Echtzeitüberwachung", "Мониторинг в реално време"),
    ("0 / 0 jobs  •  0 successful  •  0 failed", "0 / 0 Aufträge  •  0 erfolgreich  •  0 fehlgeschlagen", "0 / 0 задачи  •  0 успешни  •  0 неуспешни"),
    ("{n} / {t} jobs  •  {ok} successful  •  {bad} failed", "{n} / {t} Aufträge  •  {ok} erfolgreich  •  {bad} fehlgeschlagen", "{n} / {t} задачи  •  {ok} успешни  •  {bad} неуспешни"),
    ("{n} / {t} jobs  •  {ok} successful  •  {bad} failed  •  {sec} s", "{n} / {t} Aufträge  •  {ok} erfolgreich  •  {bad} fehlgeschlagen  •  {sec} s", "{n} / {t} задачи  •  {ok} успешни  •  {bad} неуспешни  •  {sec} s"),
    ("Execution log:", "Ausführungsprotokoll:", "Дневник на изпълнението:"),
    ("Each job uses the original Pipeline and the mandatory TSA START/STOP checks. A failed job is never marked as PASS.", "Jeder Auftrag nutzt die originale Pipeline und die verbindlichen TSA-START/STOP-Prüfungen. Ein fehlgeschlagener Auftrag wird nie als BESTANDEN markiert.", "Всяка задача използва оригиналния Pipeline и задължителните TSA START/STOP проверки. Неуспешна задача не се отбелязва като PASS."),
    ("Ready", "Bereit", "Готов"),
    ("Running…", "Läuft…", "Работи…"),
    ("Stopping…", "Wird gestoppt…", "Спиране…"),
    ("Stop request sent", "Abbruchanforderung gesendet", "Изпратена заявка за прекратяване"),
    ("Processed {n}/{t}", "Verarbeitet {n}/{t}", "Обработени {n}/{t}"),
    ("Done: {ok}/{t} PASS", "Fertig: {ok}/{t} BESTANDEN", "Готово: {ok}/{t} PASS"),
    ("Plan: {n} jobs", "Plan: {n} Aufträge", "План: {n} задачи"),
    ("Results: {path}", "Ergebnisse: {path}", "Резултати: {path}"),
    ("missing / inaccessible", "fehlt / nicht zugänglich", "липсва / недостъпен"),
    ("Select files from a single directory.", "Wählen Sie Dateien aus einem einzigen Verzeichnis.", "Изберете файлове от една директория."),
    ("New directory", "Neues Verzeichnis", "Нова директория"),
    ("The files are from another folder. Replace the current list?", "Die Dateien stammen aus einem anderen Ordner. Aktuelle Liste ersetzen?", "Файловете са от друга папка. Да се замени текущият списък?"),
    ("Add files for the report", "Dateien für den Bericht hinzufügen", "Добави файлове за отчета"),
    ("Add at least one file using “Add files…”.", "Fügen Sie mindestens eine Datei über „Dateien hinzufügen…“ hinzu.", "Добавете поне един файл чрез „Добави файлове…“."),
    ("Invalid plan", "Ungültiger Plan", "Невалиден план"),
    ("Confirmation", "Bestätigung", "Потвърждение"),
    ("Start {n} jobs with mandatory TSA?", "{n} Aufträge mit verbindlicher TSA starten?", "Да започнат ли {n} задачи със задължителен TSA?"),
    ("Active job", "Aktiver Auftrag", "Активна задача"),
    ("Press Stop first and wait for completion.", "Drücken Sie zuerst Stopp und warten Sie auf den Abschluss.", "Първо натиснете Спри и изчакайте приключването."),
    # ---- hash report generator launcher --------------------------------
    ("Combined report", "Kombinierter Bericht", "Комбиниран отчет"),
    ("Single report", "Einzelbericht", "Единичен отчет"),
    ("Extract RFC 3161", "RFC 3161 extrahieren", "Извличане на RFC 3161"),
    ("Verify RFC 3161", "RFC 3161 prüfen", "Проверка на RFC 3161"),
    ("Verify SQLite", "SQLite prüfen", "Проверка на SQLite"),
    ("TSA diagnostic", "TSA-Diagnose", "TSA диагностика"),
    ("Select an evidence folder or an EML file.", "Wählen Sie einen Nachweisordner oder eine EML-Datei.", "Изберете evidence папка или EML файл."),
    ("Select a file for an individual HASHREPORT.", "Wählen Sie eine Datei für einen individuellen HASHREPORT.", "Изберете файл за индивидуален HASHREPORT."),
    ("Select HASHREPORT.pdf. Artefacts are extracted into a separate folder.", "Wählen Sie HASHREPORT.pdf. Artefakte werden in einen separaten Ordner extrahiert.", "Изберете HASHREPORT.pdf. Артефактите се извличат в отделна папка."),
    ("Select HASHREPORT.pdf for offline RFC 3161 verification.", "Wählen Sie HASHREPORT.pdf für die Offline-RFC-3161-Prüfung.", "Изберете HASHREPORT.pdf за offline RFC 3161 проверка."),
    ("Select hash_report_evidence.sqlite3.", "Wählen Sie hash_report_evidence.sqlite3.", "Изберете hash_report_evidence.sqlite3."),
    ("Checks OpenSSL, TSA endpoints and RFC 3161 failover.", "Prüft OpenSSL, TSA-Endpunkte und RFC-3161-Failover.", "Проверява OpenSSL, TSA endpoints и RFC 3161 failover."),
    ("GUI launcher – the core modules remain unchanged", "GUI-Starter – die Kernmodule bleiben unverändert", "GUI стартер – основните модули остават непроменени"),
    ("Input", "Eingabe", "Вход"),
    ("Functions", "Funktionen", "Функции"),
    ("Select a function and an input file/folder.", "Wählen Sie eine Funktion und eine Eingabedatei/einen Eingabeordner.", "Изберете функция и входен файл/папка."),
    ("Output / Log", "Ausgabe / Protokoll", "Изход / Log"),
    ("Clear log", "Protokoll leeren", "Изчисти log"),
    ("Select a file", "Datei wählen", "Изберете файл"),
    ("Select a folder", "Ordner wählen", "Изберете папка"),
    ("Missing input", "Eingabe fehlt", "Липсва вход"),
    ("Select a file or folder.", "Wählen Sie eine Datei oder einen Ordner.", "Изберете файл или папка."),
    ("Error", "Fehler", "Грешка"),
    ("The path does not exist:", "Der Pfad existiert nicht:", "Пътят не съществува:"),
    ("You must select a file for this function.", "Für diese Funktion müssen Sie eine Datei wählen.", "За тази функция трябва да изберете файл."),
    ("Select a PDF file.", "Wählen Sie eine PDF-Datei.", "Изберете PDF файл."),
    ("The file does not have a standard SQLite extension. Continue?", "Die Datei hat keine Standard-SQLite-Endung. Fortfahren?", "Файлът няма стандартно SQLite разширение. Да продължа ли?"),
    ("Combined mode accepts an evidence folder or an EML file.\nFor an arbitrary single file use Single report.", "Der Combined-Modus akzeptiert einen Nachweisordner oder eine EML-Datei.\nFür eine beliebige Einzeldatei verwenden Sie Einzelbericht.", "Combined mode приема evidence папка или EML файл.\nЗа произволен единичен файл използвайте Single report."),
    ("Running: {title} …", "Wird ausgeführt: {title} …", "Изпълнява се: {title} …"),
    ("Error: {title}", "Fehler: {title}", "Грешка: {title}"),
    ("Failed: {title} (code {rc})", "Fehlgeschlagen: {title} (Code {rc})", "Неуспешно: {title} (код {rc})"),
    ("Done: {title}", "Fertig: {title}", "Готово: {title}"),
    ("The check did not complete successfully", "Die Prüfung wurde nicht erfolgreich abgeschlossen", "Проверката не завърши успешно"),
    ("{title} finished with code {rc}.\nSee the log for details.", "{title} endete mit Code {rc}.\nDetails siehe Protokoll.", "{title} приключи с код {rc}.\nВижте Log за подробности."),
    ("{title} finished successfully.", "{title} erfolgreich abgeschlossen.", "{title} приключи успешно."),
    ("{title} finished successfully.\n\nResult:\n{target}", "{title} erfolgreich abgeschlossen.\n\nErgebnis:\n{target}", "{title} приключи успешно.\n\nРезултат:\n{target}"),
    ("Open file", "Datei öffnen", "Отвори файла"),
    ("Show in folder", "Im Ordner anzeigen", "Покажи в папката"),
    ("Done", "Fertig", "Готово"),
    ("OK", "OK", "OK"),
    ("Missing module: {name}", "Modul fehlt: {name}", "Липсва модул: {name}"),
    # ---- Selection panel (page 05) and its indicator on the run page -------
    ("Selection", "Auswahl", "Избор"),
    ("Selection & Filters", "Auswahl & Filter", "Избор и филтри"),
    ("Filter evidence by file type", "Nachweise nach Dateityp filtern",
     "Филтриране на доказателствата по тип файл"),
    ("Choose what becomes evidence", "Wählen Sie, was zum Nachweis wird",
     "Изберете какво да стане доказателство"),
    ("Pick a folder, add file-type filters and see exactly which files a report would cover. Nothing is hashed until the report is generated.",
     "Wählen Sie einen Ordner, ergänzen Sie Dateitypfilter und sehen Sie genau, welche Dateien ein Bericht abdecken würde. Nichts wird gehasht, bevor der Bericht erzeugt wird.",
     "Изберете папка, добавете филтри за тип файл и вижте точно кои файлове ще покрие отчетът. Нищо не се хешира, докато отчетът не бъде генериран."),
    ("1  -  Folder scope", "1  -  Ordnerbereich", "1  -  Обхват на папката"),
    ("2  -  File type filters", "2  -  Dateitypfilter", "2  -  Филтри за тип файл"),
    ("3  -  Preview", "3  -  Vorschau", "3  -  Преглед"),
    ("One pattern per field, e.g. *eml.pdf or invoices/*. Type into a field and the next one appears. Patterns are combined with OR; an empty list means every file.",
     "Ein Muster pro Feld, z. B. *eml.pdf oder invoices/*. Sobald Sie ein Feld ausfüllen, erscheint das nächste. Muster werden mit ODER verknüpft; eine leere Liste bedeutet jede Datei.",
     "Един шаблон на поле, напр. *eml.pdf или invoices/*. Щом въведете в поле, се появява следващото. Шаблоните се свързват с ИЛИ; празен списък означава всеки файл."),
    ("Scan now", "Jetzt scannen", "Сканирай сега"),
    ("Scanning...", "Scannen...", "Сканиране..."),
    ("Scanning {path}", "Scannen: {path}", "Сканиране: {path}"),
    ("Scanned {count} candidate file(s).", "{count} geeignete Datei(en) gefunden.",
     "Намерени са {count} подходящи файла."),
    ("Scan failed:", "Scannen fehlgeschlagen:", "Сканирането е неуспешно:"),
    ("No folder selected.", "Kein Ordner gewählt.", "Не е избрана папка."),
    ("Choose an existing folder first.", "Wählen Sie zuerst einen vorhandenen Ordner.",
     "Първо изберете съществуваща папка."),
    ("No candidate files found.", "Keine geeigneten Dateien gefunden.",
     "Не са намерени подходящи файлове."),
    ("{count} selected of {total} ({excluded} filtered out)",
     "{count} von {total} gewählt ({excluded} herausgefiltert)",
     "{count} избрани от {total} ({excluded} отфилтрирани)"),
    ("Showing the first {count} of {total} file(s).",
     "Es werden die ersten {count} von {total} Datei(en) angezeigt.",
     "Показани са първите {count} от {total} файла."),
    ("FILTER_MATCHED_NO_FILES: these filters match nothing; the generator would refuse.",
     "FILTER_MATCHED_NO_FILES: Diese Filter treffen nichts; der Generator würde ablehnen.",
     "FILTER_MATCHED_NO_FILES: тези филтри не съвпадат с нищо; генераторът би отказал."),
    ("Clear filters", "Filter leeren", "Изчисти филтрите"),
    ("Copy list", "Liste kopieren", "Копирай списъка"),
    ("No file type filter - every file is evidence.",
     "Kein Dateitypfilter - jede Datei ist Nachweis.",
     "Няма филтър за тип файл - всеки файл е доказателство."),
    ("{count} active: {value}", "{count} aktiv: {value}", "{count} активни: {value}"),
    ("Filters cleared.", "Filter geleert.", "Филтрите са изчистени."),
    ("Nothing to copy.", "Nichts zu kopieren.", "Няма какво да се копира."),
    ("Clipboard unavailable.", "Zwischenablage nicht verfügbar.", "Клипбордът не е достъпен."),
    ("Copied {count} path(s) to the clipboard.",
     "{count} Pfad(e) in die Zwischenablage kopiert.",
     "{count} път(я) копирани в клипборда."),
    ("Relative path", "Relativer Pfad", "Относителен път"),
    ("Type", "Typ", "Тип"),
    ("Size (KB)", "Größe (KB)", "Размер (KB)"),
    ("Apply to main panel", "Auf das Hauptfenster anwenden", "Приложи в главния панел"),
    ("Generate report from selection", "Bericht aus der Auswahl erzeugen",
     "Генерирай отчет от избора"),
    ("Applied to the main panel:", "Auf das Hauptfenster angewendet:",
     "Приложено в главния панел:"),
    ("File type filter:", "Dateitypfilter:", "Филтър за тип файл:"),
    ("none - every file in the folder is evidence",
     "keine - jede Datei im Ordner ist Nachweis",
     "няма - всеки файл в папката е доказателство"),
    ("{value}  (ignored for a single file)", "{value}  (bei einer Einzeldatei ignoriert)",
     "{value}  (игнорира се за единичен файл)"),
    ("Clear", "Leeren", "Изчисти"),
    ("Edit in Selection", "In der Auswahl bearbeiten", "Редактирай в Избора"),
    ("ChronoSeal Selection", "ChronoSeal Auswahl", "ChronoSeal Избор"),
    ("The generator cannot start without a folder that exists.",
     "Der Generator kann ohne einen vorhandenen Ordner nicht starten.",
     "Генераторът не може да стартира без съществуваща папка."),
    ("Selection applied to the main panel.",
     "Auswahl auf das Hauptfenster angewendet.",
     "Изборът е приложен в главния панел."),
    ("Startup qualification has not passed yet, so the report was not started. Open Report & TSA and press Generate once qualification passes.",
     "Die Startqualifikation ist noch nicht bestanden, daher wurde der Bericht nicht gestartet. Öffnen Sie Bericht & TSA und drücken Sie Erzeugen, sobald die Qualifikation bestanden ist.",
     "Стартовата квалификация още не е премината, затова отчетът не беше стартиран. Отворете Отчет и TSA и натиснете Генерирай, след като квалификацията премине."),
]

_MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
    "bg": ["яну", "фев", "мар", "апр", "май", "юни", "юли", "авг", "сеп", "окт", "ное", "дек"],
}

_current = DEFAULT_LANGUAGE
_exact: dict[str, int] = {}
_fold: dict[str, int] = {}
_templates: list[tuple[re.Pattern, int, str]] = []
_listeners = []
_installed = False


def _build_index():
    for idx, entry in enumerate(CATALOG):
        for code, text in zip(LANGUAGES, entry):
            _exact.setdefault(text, idx)
            _fold.setdefault(text.casefold(), idx)
            if "{" in text:
                pattern = "".join(
                    "(?P<%s>.+?)" % part[1:-1] if part.startswith("{") else re.escape(part)
                    for part in re.split(r"(\{\w+\})", text) if part
                )
                _templates.append((re.compile("^" + pattern + "$", re.S), idx, code))


_build_index()


def language() -> str:
    return _current


def _render(entry, lang, values):
    text = entry[list(LANGUAGES).index(lang)]
    return text.format(**values) if values else text


def translate(text, lang=None):
    """Return text in the requested language; unknown text is returned unchanged."""
    if not isinstance(text, str) or not text.strip():
        return text
    lang = lang or _current
    lead, core, tail = re.match(r"^(\s*)(.*?)(\s*)$", text, re.S).groups()
    idx = _exact.get(core)
    if idx is not None:
        return lead + _render(CATALOG[idx], lang, None) + tail
    folded = _fold.get(core.casefold())
    if folded is not None:
        out = _render(CATALOG[folded], lang, None)
        return lead + (out.upper() if core.isupper() else out) + tail
    for pattern, idx, _code in _templates:
        match = pattern.match(core)
        if match:
            values = {k: translate(v, lang) for k, v in match.groupdict().items()}
            return lead + _render(CATALOG[idx], lang, values) + tail
    if "\n" in core:
        return lead + "\n".join(translate(line, lang) for line in core.split("\n")) + tail
    if ": " in core:
        head, _, rest = core.partition(": ")
        if head + ":" in _exact:
            return lead + translate(head + ":", lang) + " " + rest + tail
    return text


def tr(text, **values):
    """Translate an English/German/Bulgarian source text, then fill {placeholders}."""
    out = translate(text)
    return out.format(**values) if values else out


def source_of(text):
    """Canonical (English) form of a displayed text; used to map combo labels to internal keys."""
    return translate(text, "en")


def _read_saved():
    try:
        code = json.loads(_SETTINGS.read_text(encoding="utf-8")).get("language")
        return code if code in LANGUAGES else DEFAULT_LANGUAGE
    except (OSError, ValueError):
        return DEFAULT_LANGUAGE


def set_language(code, persist=True):
    global _current
    if code not in LANGUAGES:
        return
    _current = code
    if persist:
        try:
            _SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            _SETTINGS.write_text(json.dumps({"language": code}, indent=2), encoding="utf-8")
        except OSError:
            pass
    for callback in list(_listeners):
        try:
            callback(code)
        except Exception:
            pass


def month_abbr(number):
    return _MONTHS[_current][number - 1]


def on_change(callback):
    _listeners.append(callback)


def apply_language(root):
    """Re-translate every existing widget, tab, combobox value and bound variable."""
    import tkinter as tk
    from tkinter import ttk

    def visit(widget):
        try:
            keys = widget.keys()
        except tk.TclError:
            return
        if "text" in keys and not isinstance(widget, (tk.Text,)):
            try:
                try:
                    has_var = bool(str(widget.cget("textvariable")))
                except tk.TclError:
                    has_var = False
                if not has_var:
                    current = str(widget.cget("text"))
                    new = translate(current)
                    if new != current:
                        widget.configure(text=new)
            except tk.TclError:
                pass
        if "textvariable" in keys:
            try:
                name = str(widget.cget("textvariable"))
                if name:
                    value = widget.getvar(name)
                    new = translate(value) if isinstance(value, str) else value
                    if new != value:
                        widget.setvar(name, new)
            except tk.TclError:
                pass
        if isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                current = widget.tab(tab, "text")
                new = translate(current)
                if new != current:
                    widget.tab(tab, text=new)
        if isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                try:
                    current = widget.heading(column, "text")
                except tk.TclError:
                    continue
                new = translate(current)
                if new != current:
                    widget.heading(column, text=new)
        if isinstance(widget, ttk.Combobox):
            values = tuple(widget.cget("values") or ())
            translated = tuple(translate(v) for v in values)
            if translated != values:
                widget.configure(values=translated)
        for child in widget.winfo_children():
            visit(child)

    visit(root)
    for top in [root] + [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]:
        try:
            current = top.title()
            new = translate(current)
            if new != current:
                top.title(new)
        except tk.TclError:
            pass


def install():
    """Patch Tk so all new widget text, titles, menus and dialogs are localised."""
    global _installed, _current
    if _installed:
        return
    _installed = True
    _current = _read_saved()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    def tr_kw(cnf, kw):
        if isinstance(cnf, dict) and isinstance(cnf.get("text"), str):
            cnf = dict(cnf, text=translate(cnf["text"]))
        if isinstance(kw.get("text"), str):
            kw["text"] = translate(kw["text"])
        return cnf

    original_init = tk.BaseWidget.__init__

    def widget_init(self, master, widgetName, cnf={}, kw={}, extra=()):
        kw = dict(kw)
        original_init(self, master, widgetName, tr_kw(cnf, kw), kw, extra)

    tk.BaseWidget.__init__ = widget_init

    original_configure = tk.Misc._configure

    def configure(self, cmd, cnf, kw):
        kw = dict(kw)
        return original_configure(self, cmd, tr_kw(cnf, kw), kw)

    tk.Misc._configure = configure

    original_title = tk.Wm.wm_title

    def wm_title(self, string=None):
        return original_title(self, translate(string) if isinstance(string, str) else string)

    tk.Wm.wm_title = wm_title
    tk.Wm.title = wm_title

    original_var_set = tk.StringVar.set

    def var_set(self, value):
        return original_var_set(self, translate(value) if isinstance(value, str) else value)

    tk.StringVar.set = var_set

    original_var_init = tk.StringVar.__init__

    def var_init(self, master=None, value=None, name=None):
        original_var_init(self, master, translate(value) if isinstance(value, str) else value, name)

    tk.StringVar.__init__ = var_init

    original_heading = ttk.Treeview.heading

    def heading(self, column, option=None, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = translate(kw["text"])
        return original_heading(self, column, option, **kw)

    ttk.Treeview.heading = heading

    original_tab_add = ttk.Notebook.add

    def tab_add(self, child, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = translate(kw["text"])
        return original_tab_add(self, child, **kw)

    ttk.Notebook.add = tab_add

    for name in ("add_command", "add_checkbutton", "add_radiobutton", "add_cascade"):
        def wrap(original):
            def add_item(self, cnf={}, **kw):
                if isinstance(kw.get("label"), str):
                    kw["label"] = translate(kw["label"])
                return original(self, cnf, **kw)
            return add_item
        setattr(tk.Menu, name, wrap(getattr(tk.Menu, name)))

    for name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel",
                 "askretrycancel", "askquestion", "askyesnocancel"):
        def wrap_box(original):
            def box(title=None, message=None, **options):
                return original(translate(title) if isinstance(title, str) else title,
                                translate(message) if isinstance(message, str) else message, **options)
            return box
        setattr(messagebox, name, wrap_box(getattr(messagebox, name)))

    for name in ("askopenfilename", "askopenfilenames", "asksaveasfilename", "askdirectory"):
        def wrap_dialog(original):
            def dialog(**options):
                if isinstance(options.get("title"), str):
                    options["title"] = translate(options["title"])
                if options.get("filetypes"):
                    options["filetypes"] = [(translate(label), pattern) for label, pattern in options["filetypes"]]
                return original(**options)
            return dialog
        setattr(filedialog, name, wrap_dialog(getattr(filedialog, name)))


def add_language_selector(parent, root, style=None, label_style=None, **pack_options):
    """Create the language drop-down and wire it to apply_language(root)."""
    import tkinter as tk
    from tkinter import ttk

    holder = ttk.Frame(parent, style=style) if style else ttk.Frame(parent)
    label = ttk.Label(holder, text="Language", **({"style": label_style} if label_style else {}))
    label.pack(side="left", padx=(0, 6))
    variable = tk.StringVar(value=LANGUAGES[_current])
    combo = ttk.Combobox(holder, textvariable=variable, values=list(LANGUAGES.values()),
                         state="readonly", width=11)
    combo.pack(side="left")

    def changed(_event=None):
        code = next((c for c, n in LANGUAGES.items() if n == variable.get()), DEFAULT_LANGUAGE)
        set_language(code)
        apply_language(root)
        label.configure(text=translate("Language"))

    combo.bind("<<ComboboxSelected>>", changed)
    holder.pack(**pack_options)
    return holder
