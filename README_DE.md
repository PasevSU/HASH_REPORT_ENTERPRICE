# GitSU SUPERUSER Enterprise Pro — Deutsch

**Entwickelt und präsentiert von PasevSU-DEV** · https://pasevsu.github.io/

## Starten (v0.43.4)

Am einfachsten: `release\GitSU-win-x64-0.43.4.zip` entpacken → `GitSU.exe` (ohne Installation). Aus dem Quellcode: `cd data\app && npm i && npm start`.

### Bereiche
Übersicht · Änderungen (Diff, Stage, Commit) · Vorgänge · Synchronisierung (Watcher + Lease) · Verlauf · Einstellungen.

### Ordner mit Repository verbinden
„Hinzufügen“ öffnet einen Dialog: Ordner, Repository und Aktion wählen — registrieren, klonen, verknüpfen (Ordner ohne Git mit Remote, Dateien bleiben unberührt), erstellen oder veröffentlichen.

### Windows ↔ Home Assistant
`gitsu-watcher-windows-0.42.0.zip` und `gitsu-watcher-ha-0.42.0.tar.gz` sichern per Lease (`refs/gitsu/lease/<Branch>`) einen einzigen Schreiber; der andere Knoten folgt mit ff-only. Synchrone Uhren (NTP) erforderlich. Windows-Autostart: `pwsh install-task.ps1`. Prüfsummen: `SHA256SUMS.txt`.

## Älterer Start (Python)

Archiv entpacken und `gui.pyw` für den grafischen Start ohne Konsole öffnen. Alternativ `gui.py` für den Python-Start oder `gui.cmd` für die Konsole verwenden. Eine GitSU-Installation ist nicht erforderlich; Python 3 mit tkinter wird benötigt. Beim ersten Start kann Internetzugang für Node.js und Electron erforderlich sein.

## Sprachen

In der oberen Leiste **Deutsch** oder **Български** wählen. Die Auswahl wird lokal gespeichert. Navigation, Kennzahlen, Schaltflächen, Status, Filter, Aktionen und Hilfetexte sind übersetzt. Technische Bezeichner und ursprüngliche Diagnosemeldungen bleiben unverändert, um die Fehlersuche nicht zu beeinträchtigen.

## Funktionen

- Lokale Git-Repositorys registrieren, prüfen und überwachen.
- Branches, lokale Änderungen und GitHub-Origin prüfen.
- Git-Vorgänge vor der Ausführung ansehen und bestätigen.
- Kopierplan vor der Dateisynchronisierung erstellen.
- Ressourcensteuerung, Vorgangsprotokoll und Systemdiagnose.

## Daten und Datenschutz

Die Anwendung arbeitet lokal. Arbeitsdaten und Caches liegen in `data/`. Git-/GitHub-Netzwerkvorgänge erfolgen bei den jeweiligen Aktionen. Das anfängliche Herunterladen von Abhängigkeiten benötigt Internetzugang.

## Einschränkungen

Dies ist ein Release Candidate. Der tatsächliche Windows-Start sowie NAS- und GitHub-Szenarien sind noch nicht vollständig qualifiziert. Wichtige Daten vor verändernden Aktionen sichern.


## Lokales Repository-Update zwischen Ordnern
Quell-Repository auswählen → „Lokales Update · Ordner → Ordner“ → Zielordner eingeben → „Prüfen“ → Änderungen kontrollieren → „Ausführen“. Neue/geänderte Dateien werden kopiert; `.git` und symbolische Links werden übersprungen. Danach erfolgt ein erneuter Vergleich. Zusätzliche Dateien im Ziel werden nicht gelöscht und Git-Historie wird nicht übertragen. Überschreibungen sind nicht transaktional: Zielordner vorher sichern.
