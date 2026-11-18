# ChronoSeal — единен графичен интерфейс

Стартирайте **Start_ChronoSeal.bat** или директно **ChronoSeal_GUI.pyw**. Това е **единственият** вход — отваря `ChronoSealDesktop` с шест раздела: Report & TSA, Report from Files, Automation, Settings & Trust, Diagnostics & Logs, Selection & Filters.

Старият код е запазен без промяна като `ChronoSeal_Original_Legacy.py` и се използва вътрешно като базов клас. `ChronoSeal_GUI.pyw` е реалният единен интерфейс.

В Automatic Reports първо се избира видът на отчета (комбиниран, индивидуален, комбиниран и индивидуален), после съответната автоматизация. Смяната на вида обновява зависимите контроли.

Това поправя несъответствието между стартирания файл и новия интерфейс. Не удостоверява успешен реален TSA процес на Windows.
