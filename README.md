GitSU SUPERUSER Enterprise Pro — v0.43.4

Български: README_BG.md
Deutsch: README_DE.md

Start: release\GitSU-win-x64-0.43.4.zip -> GitSU.exe (no install),
       or from source: cd data\app && npm i && npm start (gui.cmd / gui.py also work).
Language: top bar, Български / Deutsch.

Tabs: Overview, Changes (diff/stage/commit), Operations, Sync (watcher + lease), History, Settings.
Connect dialog: pick folder + repository + action (register / clone / link / create / publish) in one step.

Watcher (Windows <-> Home Assistant): release\gitsu-watcher-windows-*.zip, release\gitsu-watcher-ha-*.tar.gz
  - Single-writer lease (refs/gitsu/lease/<branch>); the other node follows with ff-only. Needs NTP-synced clocks.
  - Windows autostart: pwsh install-task.ps1 [-Status|-Remove]. Configure watcher.env first.
  - See watcher-package\README-*.md and WATCHER_INTEGRATION_BG.md.

Verification: python release_gate.py. Externally-evidenced checks stay BLOCKED until real evidence is supplied.
Known: 2 tests fail only on this Windows host (symlink EPERM, gh already authenticated).
Verify downloads with release\SHA256SUMS.txt.