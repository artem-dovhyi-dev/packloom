# Межа між плагіном і даними збірки: що з techpack переїжджає, а що лишається

Type: grilling
Status: resolved
Blocked by: 02

## Question

Для кожного файлу techpack/modpack (build.py, smoke-test.py, quests/gen_quests.py, quests/build_index.py,
mods.txt, overrides/, server/, wayfinder/, MODLIST.md, build-report.md) вирішити: переїжджає в плагін як
загальний код, лишається в techpack як дані, чи розділяється на обидва. Окремо: де живе pack.json з
GAME/LOADER/PACK_NAME/PACK_VERSION, які зараз зашиті в build.py, і як скрипт плагіна знаходить папку збірки.
Результат: таблиця файлів з рішенням і схема папок techpack після міграції.

## Answer

Межа: плагін = код, що не знає назв модів; techpack = усе, де є назви модів, квести чи правила.

| Файл techpack/modpack | Рішення |
|---|---|
| build.py | у плагін як `lib/packloom/build.py`; константи GAME/LOADER/PACK_* переходять у `pack.json` збірки; FTB_MODS більше не зашиті, а описані в mods.txt |
| smoke-test.py | у плагін як `lib/packloom/smoke.py`; додається JSON-звіт і автоустановка Forge-сервера (раніше вручну) |
| quests/build_index.py | у плагін пізніше (`pack-registry`): це загальний індекс ID із jar; поки лишається |
| quests/gen_quests.py | розділити пізніше: SNBT-писар і валідатор у плагін, дані квестів у techpack; зараз не чіпати, щоб не зламати робочий квестбук |
| mods.txt | лишається в techpack, переводиться на синтаксис із тікета 06 (сумісний зі старим: голий слаг працює як раніше) |
| pack.json | новий файл у techpack поруч із mods.txt |
| overrides/ | дані, techpack; `overrides/mods` наповнюється плагіном з `ftb:`/`url:` рядків |
| server/ | згенероване, techpack, у .gitignore майбутнього репозиторію техпаку |
| build-report.md, *.mrpack, smoke-test.log | згенероване, techpack |
| MODLIST.md, README.md, wayfinder/ | techpack |

Папка збірки знаходиться так: аргумент `--pack <dir>`, інакше поточна тека, інакше перша тека з `pack.json`
у проєкті. Старі скрипти в techpack лишаються, доки плагін не збере той самий mrpack; після цього їх видаляємо.

## Comments

- 2026-11-05 02:15: виконано. build.py і smoke-test.py перенесені в `lib/packloom` (build.py, server.py, triage.py); techpack отримав `pack.json`, FTB-моди і Flux Networks переписані на `ftb:`/`manual:`; плагін зібрав mrpack з ідентичним індексом (80 файлів, ті самі хеші, env і overrides). `.claude/settings.json` у techpack підключає плагін з GitHub. Старі скрипти лишаються до кількох успішних збірок.
