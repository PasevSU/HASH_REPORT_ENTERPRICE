# ChronoSeal v90 — прецизна централна миграция (NOT RELEASE)

Еталон: `стандарт(9).pdf`, стр. 1. Запазени са текстът, правният панел, QR, SYSTEM INFORMATION, VOLUME, footer и хешовете.

## Променени правила
- `CENTRAL_LAYOUT.title.separator_height_pt`: 2 pt, вместо `rowHeights=[2]` в Python.
- `CENTRAL_LAYOUT.legal_qr.image_horizontal_alignment`: CENTER, вместо локални стойности в SINGLE/COMBO.
- Запазени от v89: `legal_qr.column_width_pt` и 4 таблични padding правила.

Това е ограничена, обратима миграция. Трите инсталационни метода `atomic`, `overlay`, `patch` от v89 са запазени. Пълна визуална и криптографска квалификация още не е извършена. RELEASE BLOCKED.
