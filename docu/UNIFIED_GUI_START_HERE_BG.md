# ChronoSeal — единен графичен интерфейс

Стартирайте **Start_ChronoSeal.bat** или **ChronoSeal_OneButton.pyw**. И двете отварят **един и същ** `ChronoSealDesktop` с четири раздела: Report & TSA, Automatic Reports, Settings & Trust, Diagnostics & Logs.

Старият код е запазен без промяна като `ChronoSeal_Original_Legacy.pyw` и се използва вътрешно. `ChronoSeal_GUI.pyw` е реалният единен интерфейс.

В Automatic Reports първо се избира видът на отчета (комбиниран, индивидуален, комбиниран и индивидуален), после съответната автоматизация. Смяната на вида обновява зависимите контроли.

Това поправя несъответствието между стартирания файл и новия интерфейс. Не удостоверява успешен реален TSA процес на Windows.
