# ChronoSeal v91 — QR semantic migration (NOT RELEASE)

Мигрирани са **8 използвания** на стари line-number-based визуални ключове в SINGLE/COMBO към общи семантични JS настройки.

- QR изображение: `image_width_pt=135`, `image_height_pt=135`
- Подравняване: `box_alignment=RIGHT`, `panel_alignment=LEFT`
- Предишните стойности са проверени и са идентични между двата генератора.
- Без промяна на криптографска логика, payload, съдържание или данни.
- Трите метода за прилагане от v89 остават в `migration_kit/apply.py`.
- Това е частична миграция, не 100% централизация; RELEASE BLOCKED.
