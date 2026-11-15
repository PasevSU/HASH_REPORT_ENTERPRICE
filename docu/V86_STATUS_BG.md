# ChronoSeal DEV v86 — обща визуална политика за SINGLE и COMBINED

- Производствените `hash_report_single.py` и `hash_report_combined.py` вече използват обща функция `apply_profile_presentation`.
- `COMBINED_PRESENTATION` е дефиниран в `style/39_combined_presentation.js`, със запазени стойности от v85.
- `SINGLE_PRESENTATION` остава в `style/99_single_presentation.js`.
- Заглавие, цвят на секция и правен текст вече се прилагат чрез еднакъв механизъм.
- При липсваща задължителна настройка се отказва генериране, вместо мълчаливо заместване.
- Криптографските алгоритми и логиката за TSA не са променяни.
- Не е доказана визуална идентичност 1:1 или end-to-end работа на четирите профила. RELEASE BLOCKED.
