# Prism Launcher на macOS: де лежать інстанси, options.txt, логи, і чи є CLI-запуск

Type: research
Status: resolved
Blocked by:

## Question

Де Prism Launcher на macOS зберігає інстанси, який шлях до options.txt, logs/latest.log, crash-reports і
instance.cfg всередині інстансу, що в instance.cfg корисного для агента (версія гри, лоадер, Java), чи можна
імпортувати mrpack і запустити інстанс з командного рядка, і чи є спосіб запуску без Microsoft-акаунта
для тесту завантаження модів. Результат: таблиця шляхів і можливостей з посиланнями на документацію або код
Prism. Потрібно для тікетів про цикл перевірки і клавіатуру.

## Answer

- Дані: `~/Library/Application Support/PrismLauncher`; інстанси в `instances/<id>/` (ID = ім'я папки, ознака інстансу — `instance.cfg`); портативного режиму на macOS немає, корінь можна змінити через `-d` або `PRISMLAUNCHER_DATA_DIR`.
- Усередині інстансу: `instance.cfg` (INI: name, Java/пам'ять override-и, ManagedPack*, lastLaunchTime), `mmc-pack.json` (версія гри = компонент `net.minecraft`, лоадер = `net.fabricmc.fabric-loader` / `org.quiltmc.quilt-loader` / `net.minecraftforge` / `net.neoforged`), гра в `minecraft/` (`.minecraft/` лише як спадок MultiMC, якщо `minecraft/` немає).
- Шляхи клієнта: `minecraft/mods`, `minecraft/config`, `minecraft/options.txt`, `minecraft/logs/latest.log`, `minecraft/crash-reports/`; логи лаунчера — `logs/PrismLauncher-0.log`.
- CLI (`Prism Launcher.app/Contents/MacOS/prismlauncher`): `-l <id>`, `-s <server>`, `-a <profile>`, `-o <name>` (offline, з 10.0), `-I <mrpack|URL>`, `--show-window`; headless-режиму немає — імпорт відкриває `NewInstanceDialog` (треба OK), помилки = модальні діалоги.
- Без MS-акаунта: offline-акаунт додати не можна; запуск без акаунтів веде в demo-режим через два діалоги (моди при цьому завантажуються) — автоматизувати не вийде, для перевірки модів краще серверний тест (тікет 04).
- Java: окремого `javas.cfg` немає; JRE інстансу — `JavaPath` в `instance.cfg` (при `OverrideJavaLocation=true`, саме туди пише автозавантаження), глобальний — `JavaPath` у `prismlauncher.cfg`; автозавантажені JRE лежать у `java/<name>/bin/java` (для Java 17 — `java/java-runtime-gamma`, на macOS це симлінки на `jre.bundle/Contents/Home`).
- Деталі, посилання на код/вікі, позначки «неперевірено»: `research/03-prism-layout.md`.

## Comments

- Перевірено локально 2026-11-05: options.txt має рядки `name:value` (наприклад `renderDistance:10`), бінди будуть `key_key.inventory:key.keyboard.e`. Java-runtime лежить у `java/java-runtime-gamma/` з `bin/java` і `jre.bundle`. Prism.app зараз у `~/Downloads/Prism Launcher.app`, не в `/Applications`; шлях до бінарника тоді `<app>/Contents/MacOS/prismlauncher`.
