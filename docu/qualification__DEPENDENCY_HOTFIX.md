# Dependency hotfix (RC, not release)
Observed Windows failure: ModuleNotFoundError: No module named fitz after report generation.
Preflight now checks fitz, pypdf, reportlab before creating an intermediate report.
Installer installs requirements-integration.txt using python.exe and verifies imports.
Outstanding: GUI pythonw.exe may resolve a different Python environment than python.exe; validate Windows paths before release.
No live START/STOP/DSS end-to-end qualification performed for this hotfix.
