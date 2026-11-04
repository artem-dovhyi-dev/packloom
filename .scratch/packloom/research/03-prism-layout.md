# Prism Launcher на macOS: шляхи, instance.cfg, CLI, Java

Дата: 2026-11-05. Джерела: гілка `develop` репозиторію PrismLauncher (посилання на raw-файли), вікі prismlauncher.org, minecraft.wiki, meta.prismlauncher.org, piston-meta.mojang.com. Prism на цьому Mac не встановлений, тому все нижче — з коду і документації, не з живої перевірки. Позначка **[неперевірено]** — факт виведений, а не прочитаний у джерелі дослівно.

Скорочення: `$DATA` = `~/Library/Application Support/PrismLauncher`; `$INST` = `$DATA/instances/<id>`; `$GAME` = `$INST/minecraft`.

## 1. Каталог даних і структура інстансу

| Що | Шлях / значення | Джерело |
|---|---|---|
| Каталог даних на macOS | `~/Library/Application Support/PrismLauncher` (таблиця "macOS" у вікі). У коді: `QStandardPaths::AppDataLocation` + `..`; portable-режим на macOS вимкнений (`#ifndef Q_OS_MACOS`). Перевизначення: `-d/--dir` або змінна `PRISMLAUNCHER_DATA_DIR` (`Launcher_ENVName` = `PRISMLAUNCHER`) | [wiki: Data Location](https://prismlauncher.org/wiki/getting-started/data-location), [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp), [program_info/CMakeLists.txt](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/program_info/CMakeLists.txt) |
| Глобальні налаштування | `$DATA/prismlauncher.cfg` (INI; `Launcher_ConfigFile = "${Launcher_APP_BINARY_NAME}.cfg"`, бінарник `prismlauncher`; fallback `polymc.cfg`, `multimc.cfg`) | [program_info/CMakeLists.txt](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/program_info/CMakeLists.txt), [CMakeLists.txt](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/CMakeLists.txt), [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| Логи самого лаунчера | `$DATA/logs/PrismLauncher-0.log` … `-4.log` (`BuildConfig.LAUNCHER_NAME + "-%0.log"`, ротація 5 файлів) | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| Папка інстансів | `$DATA/instances` (setting `InstanceDir`, default `"instances"`). У `develop` підтримується кілька коренів (`m_instDirs`); інстанс = підпапка, в якій є `instance.cfg`; **ID інстансу = ім'я папки** (`QFileInfo(instanceRoot()).fileName()`) | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp), [InstanceList.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/InstanceList.cpp), [BaseInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/BaseInstance.cpp), [wiki: CLI](https://prismlauncher.org/wiki/getting-started/command-line-interface) |
| Групи інстансів | `instgroups.json` (новий: у робочому каталозі лаунчера = `$DATA`; legacy: `$DATA/instances/instgroups.json`) | [InstanceList.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/InstanceList.cpp) |
| Інші папки `$DATA` | `java` (керовані лаунчером JRE; `JavaDir` default `"java"`), `icons`, `mods` (central mods, `CentralModsDir`), `skins`, `libraries`, `assets`, `meta` | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp), [wiki: Data Location](https://prismlauncher.org/wiki/getting-started/data-location) (`libraries/assets/meta` — **[неперевірено]** по коду, лише загальновідомо) |
| `instance.cfg` | `$INST/instance.cfg` (INI; `FS::PathCombine(instanceRoot, "instance.cfg")`) | [InstanceList.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/InstanceList.cpp) |
| `mmc-pack.json` | `$INST/mmc-pack.json` — список компонентів (версія гри, лоадер) | [PackProfile.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/PackProfile.cpp) |
| `minecraft/` чи `.minecraft/` | `gameRoot()`: повертає `$INST/.minecraft` **тільки якщо** `.minecraft` існує, а `minecraft` — ні; інакше `$INST/minecraft`. Тобто нові інстанси Prism = `minecraft/`; `.minecraft/` — спадок MultiMC. Агенту треба перевіряти обидва в тому ж порядку | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| Моди | `$GAME/mods` (`modsRoot()`); також `coremods`, `nilmods` | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| Конфіги модів | `$GAME/config` (`instanceConfigFolder()`) | там само |
| Ресурс-/шейдер-паки, світи | `$GAME/resourcepacks`, `$GAME/shaderpacks`, `$GAME/texturepacks`, `$GAME/saves`, датапаки `$GAME/datapacks` (або `GlobalDataPacksPath`) | там само |
| `options.txt` | `$GAME/options.txt` — Prism не чіпає його; це стандартний файл клієнта в кореневій папці гри (на minecraft.wiki: "It is found in the .minecraft folder"). **[неперевірено в коді Prism]** — виведено з того, що `gameRoot()` і є `.minecraft` для клієнта | [minecraft.wiki: Options.txt (Java Edition)](https://minecraft.wiki/w/Options.txt_(Java_Edition)) |
| Логи гри | `$GAME/logs/latest.log`; `getLogFileSearchPaths()` повертає `crash-reports`, `logs` і `gameRoot()` | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| Краш-репорти | `$GAME/crash-reports/` | там само |
| Поза `$GAME` | `$INST/jarmods/`, `$INST/natives/`, `$INST/libraries/` (локальні) | там само |

## 2. Корисні ключі в `instance.cfg` (INI, секція `[General]`)

Значення, що залежать від глобальних, пишуться в інстанс лише при `Override*=true`.

| Ключ | Значення / default | Для чого агенту | Джерело |
|---|---|---|---|
| `InstanceType` | `OneSix` (інакше інстанс відхиляється) | sanity-check | [InstanceList.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/InstanceList.cpp) |
| `name`, `iconKey`, `notes`, `uuid` | `"Unnamed Instance"`, `"default"`, `""`, UUID | людська назва ≠ ID папки | [BaseInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/BaseInstance.cpp) |
| `lastLaunchTime`, `totalTimePlayed`, `lastTimePlayed` | епоха/секунди | "чи запускався інстанс після змін" | там само |
| `ManagedPack`, `ManagedPackType`, `ManagedPackID`, `ManagedPackName`, `ManagedPackVersionID`, `ManagedPackVersionName`, `ManagedPackURL` | bool / рядки | інстанс з імпортованого mrpack/CurseForge-паку | там само |
| `OverrideJavaLocation` + `JavaPath`, `IgnoreJavaCompatibility` | bool + шлях до `java` | який JRE використовує інстанс (саме сюди AutoInstallJava записує завантажений JRE) | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp), [AutoInstallJava.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/launch/AutoInstallJava.cpp) |
| `OverrideJavaArgs` + `JvmArgs` | bool + рядок | JVM-аргументи | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| `AutomaticJava` | bool | JRE вибрано автоматично | там само |
| `JavaVersion`, `JavaArchitecture`, `JavaRealArchitecture`, `JavaVendor`, `JavaSignature` | passthrough-кеш | версія JRE без запуску `java -version` | там само |
| `OverrideMemory` + `MinMemAlloc`, `MaxMemAlloc`, `PermGen` | MiB (глобальні дефолти 512 / `SysInfo::defaultMaxJvmMem()` / 128) | пам'ять | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp), [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| `OverrideWindow` + `LaunchMaximized`, `MinecraftWinWidth`, `MinecraftWinHeight` | | розмір вікна | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| `JoinServerOnLaunch`, `JoinServerOnLaunchAddress`, `JoinWorldOnLaunch` | | автоприєднання | там само |
| `UseAccountForInstance`, `InstanceAccountId` | | акаунт для інстансу | там само |
| `OverrideCommands`, `PreLaunchCommand`, `PostExitCommand` (через OverrideCommands), `OverrideConsole`, `CloseAfterLaunch`, `QuitAfterGameStop` | | хуки запуску | [BaseInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/BaseInstance.cpp), [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| `ExportName`, `ExportVersion`, `ExportAuthor`, `ExportSummary`, `ExportOptionalFiles`, `ExportRecommendedRAM` | | метадані для експорту в mrpack | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |

Версія гри і лоадер **не** в `instance.cfg`, а в `mmc-pack.json`.

## 3. `mmc-pack.json`

| Поле | Опис | Джерело |
|---|---|---|
| `formatVersion` | завжди `1` (інше відхиляється) | [PackProfile.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/PackProfile.cpp) |
| `components[]` | масив; кожен: `uid` (обов'язково), `version`, `cachedName`, `cachedVersion`, `cachedRequires`, `cachedConflicts`, `important`, `dependencyOnly`, `disabled`, `cachedVolatile` (записується як `cachedVolatile`, читається як `volatile` — неузгодженість у коді) | там само |
| Версія гри | компонент `uid: "net.minecraft"`, поле `version` | там само |
| Лоадери (`Component::KNOWN_MODLOADERS`) | `net.fabricmc.fabric-loader` → Fabric; `org.quiltmc.quilt-loader` → Quilt; `net.minecraftforge` → Forge; `net.neoforged` → NeoForge; `com.mumfrey.liteloader` → LiteLoader. Увага: Quilt вважається сумісним з Fabric; на 1.20.1 NeoForge вважається сумісним з Forge | [Component.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/Component.cpp), [PackProfile.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/PackProfile.cpp) |
| Інші uid | `org.lwjgl`/`org.lwjgl3`, `net.minecraft.java` (JRE-індекс мети) — **[неперевірено]** для lwjgl | [meta.prismlauncher.org net.minecraft.java](https://meta.prismlauncher.org/v1/net.minecraft.java/index.json) |

## 4. CLI (`Application.cpp`, гілка `develop`; вікі відстає — у ній немає `--offline` і `--world`)

Бінарник на macOS: `/Applications/Prism Launcher.app/Contents/MacOS/prismlauncher` — **[неперевірено]**, вікі дає лише `Usage: prismlauncher ...`; шлях виведено з `Launcher_APP_BINARY_NAME = "prismlauncher"` і `${Launcher_Name}.app`.

| Опція | Опис (з коду) | Джерело |
|---|---|---|
| `-d, --dir <directory>` | інший корінь даних | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| `-l, --launch <instance>` | запустити інстанс **за ID (ім'я папки)** | там само, [wiki: CLI](https://prismlauncher.org/wiki/getting-started/command-line-interface) |
| `-s, --server <address>` | приєднатися до сервера (тільки з `--launch`) | там само |
| `-w, --world <world>` | зайти у світ (тільки з `--launch`; перевірка "only with --launch" цей прапорець не охоплює) | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| `-a, --profile <profile>` | акаунт за ім'ям профілю (тільки з `--launch`); якщо профіль не знайдено — старт мовчки припиняється | там само |
| `-o, --offline <name>` | "Launch offline, with given player name" (тільки з `--launch`). Додано PR #2331, milestone 10.0 (злито 2024-10-30) | там само, [PR #2331](https://github.com/PrismLauncher/PrismLauncher/pull/2331) |
| `-I, --import <url>` / позиційні `URL...` | імпорт інстансу або ресурсу з локального шляху чи URL | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| `--show <instance>` | відкрити вікно інстансу | там само |
| `--show-window` | показати головне вікно (разом із `--launch`) | там само |
| `--alive` | записати `live.check` після старту | там само |

Якщо лаунчер уже запущений, аргументи пересилаються у живий процес (`launch.args["id"/"server"/"profile"/"offline_enabled"/"offline_name"]`).

**Headless-режиму немає**: `--launch` без `--show-window` ховає головне вікно, але Qt-GUI усе одно стартує; будь-яка помилка/вибір акаунта = модальний діалог.

### Імпорт mrpack

`--import <шлях|URL>` → `MainWindow::processURLs`: тип файлу визначається вмістом (`ResourceUtils::identify`), не розширенням; для інстансу/модпаку відкривається **`NewInstanceDialog` (`exec()`, треба натиснути OK)**; `https://…` спершу завантажується з діалогом прогресу; `modrinth://` приймає лише modpack-посилання; `curseforge://` потребує `addonId`+`fileId`. Тобто імпорт з CLI **інтерактивний**, автоматизувати без GUI не можна. Джерело: [MainWindow.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/ui/MainWindow.cpp).

Для агента безпечніша альтернатива: не імпортувати через Prism, а самому створити `$INST/instance.cfg` (`InstanceType=OneSix`, `name=`) + `mmc-pack.json` (`net.minecraft` + лоадер) + `minecraft/mods`; Prism підхопить папку при скануванні (критерій — наявність `instance.cfg`). **[неперевірено на практиці]**, виведено з `discoverInstances` і `loadInstance`.

### Запуск без Microsoft-акаунта

| Сценарій | Що відбувається | Джерело |
|---|---|---|
| Акаунтів нема, `--launch` | `decideAccount()` показує "No Accounts" (пропозиція відкрити налаштування), потім `decideLaunchMode()` дає `LaunchMode::Demo`, `askPlayDemo()` питає "No account was selected for launch… play demo?" (default Cancel), далі діалог імені. Якщо погодитись — `AuthSession::MakeDemo`, гра стартує з `--demo`. Тільки ≥ 1.3.1 (`supportsDemo()`) | [LaunchController.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/LaunchController.cpp), [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| Demo-режим і моди | моди/лоадер завантажуються як звичайно (режим мережі для demo = Online, assets/libraries оновлюються); обмеження demo стосуються лише ігрового контенту. Для "чи завантажились моди до головного меню" demo достатньо — **[неперевірено на живому Prism]**, виведено з `createLaunchTask` | [MinecraftInstance.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/MinecraftInstance.cpp) |
| Додати Offline-акаунт | **заборонено без MSA**: "You must add a Microsoft account that owns Minecraft before you can add an offline account." | [AccountListPage.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/ui/pages/global/AccountListPage.cpp) |
| `--offline <name>` без акаунта | потребує існуючого акаунта, що володіє грою; інакше падає в Demo (з тими ж діалогами) | [LaunchController.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/LaunchController.cpp) |
| Повністю без GUI | неможливо: і demo, і "No Accounts" — модальні QMessageBox/QInputDialog | там само |

Висновок: автоматичний (без кліків) запуск клієнта через Prism без MS-акаунта **не існує**. Для перевірки завантаження модів без акаунта надійніший шлях — серверний тест (тікет 04) з Java Prism'а, або demo вручну з GUI.

## 5. Java: як Prism зберігає і де лежить його JRE

| Що | Деталі | Джерело |
|---|---|---|
| Глобальний JRE | `prismlauncher.cfg`: `JavaPath` (default `""`), `JavaVersion`, `JavaArchitecture`, `JavaRealArchitecture`, `JavaVendor`, `JavaSignature`, `JvmArgs`, `IgnoreJavaCompatibility`, `IgnoreJavaWizard`, `AutomaticJavaSwitch` і `AutomaticJavaDownload` (обидва ввімкнені за замовчуванням, якщо `JavaPath` порожній), `UserAskedAboutAutomaticJavaDownload`, `MinMemAlloc=512`, `MaxMemAlloc`, `PermGen=128`, `JavaDir="java"` | [Application.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/Application.cpp) |
| Файлу `javas.cfg` **немає** | окремого реєстру JRE нема; є лише `JavaPath` глобально, `JavaPath` в `instance.cfg` (при `OverrideJavaLocation=true`) і закріплені шляхи за мажорною версією (`JavaUtils::getPinnedPath(major)` — ключ у cfg **[неперевірено]**) | [AutoInstallJava.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/launch/AutoInstallJava.cpp) |
| Автозавантаження (Prism ≥ 9.0) | індекс `net.minecraft.java` з meta.prismlauncher.org: `java8`, `java16`, `java17`, `java21`, `java25`; для macOS (`mac-os-x64`, `mac-os-arm64`) — vendor `mojang`, `downloadType: manifest`, `piston-meta.mojang.com`; імена рантаймів для 17: `java-runtime-gamma` (також `-beta`, `-alpha`, `-gamma-snapshot`) | [wiki: Java](https://prismlauncher.org/wiki/getting-started/installing-java/), [index.json](https://meta.prismlauncher.org/v1/net.minecraft.java/index.json), [java17.json](https://meta.prismlauncher.org/v1/net.minecraft.java/java17.json) |
| Куди кладе | `$DATA/java/<name>/` (`javaDir.absoluteFilePath(java->m_name)`), де `<name>` = `compatibleJavaName` з version-json інстансу (напр. `java-runtime-gamma` для Java 17). Манифест Mojang для macOS розпаковує в `jre.bundle/Contents/Home/bin/java`; після цього `Java::SymlinkTask` робить симлінки `<final>/bin`, `<final>/lib`… → `jre.bundle/Contents/Home/*`. Тож **`$DATA/java/java-runtime-gamma/bin/java`** існує (симлінк) — саме так Prism перевіряє "вже встановлено" (`<name>/bin/java`) | [AutoInstallJava.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/launch/AutoInstallJava.cpp), [SymlinkTask.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/java/download/SymlinkTask.cpp), [Mojang manifest mac-os-arm64 gamma](https://piston-meta.mojang.com/v1/packages/e0c8d5ccfe8cfb38075ff1b7f6352d7b03fd7868/manifest.json), [all.json](https://piston-meta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json) |
| Після автозавантаження | у `instance.cfg`: `OverrideJavaLocation=true`, `JavaPath=<шлях>`, `AutomaticJava=true` — тобто **найпростіший спосіб дізнатись JRE інстансу — прочитати `JavaPath` з його `instance.cfg`**, fallback — `JavaPath` з `prismlauncher.cfg` | [AutoInstallJava.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/launch/AutoInstallJava.cpp) |
| Де Prism шукає JRE на macOS (autodetect) | `java` з PATH; `/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/java` (і `…/jre/bin/java`); `/System/Library/Java/JavaVirtualMachines/*`; `~/Library/Java/JavaVirtualMachines/*`; `~/.sdkman/candidates/java/*`; `~/.asdf/installs/java/*`; `~/Library/Application Support/minecraft/runtime/**/bin/java` (офіційний лаунчер); `$DATA/java/*/{jre/bin,bin,.}/java`; змінна `PRISMLAUNCHER_JAVA_PATHS` (через `:`). Homebrew-шляхи не скануються | [JavaUtils.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/java/JavaUtils.cpp) |
| Яка Java якій грі | Java 8 — ≤1.16; Java 17 — 1.17–1.20.4; Java 21 — ≥1.20.5 (вікі). Точне значення для інстансу — `compatibleJavaMajors` у version-json (`$DATA/meta/net.minecraft/<ver>.json` — **[неперевірено]** шлях) | [wiki: Java](https://prismlauncher.org/wiki/getting-started/installing-java/), [LaunchProfile.cpp](https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/launcher/minecraft/LaunchProfile.cpp) |

Рецепт для серверного тесту (тікет 04): узяти `JavaPath` з `instance.cfg` → інакше `JavaPath` з `prismlauncher.cfg` → інакше glob `$DATA/java/*/bin/java` і вибрати за `java -version` → інакше `/Library/Java/JavaVirtualMachines/*/Contents/Home/bin/java`.

## 6. `options.txt` (клієнт)

| Факт | Джерело |
|---|---|
| Лежить у кореневій папці гри (`.minecraft`, у Prism — `$GAME`); редагується текстовим редактором; більшість опцій дублюються в меню | [minecraft.wiki](https://minecraft.wiki/w/Options.txt_(Java_Edition)) |
| Поле `version` — data version клієнта, що останнім зберіг файл; якщо відсутнє — файл замінюється дефолтним; старіша версія гри може скинути налаштування | там само |
| Клавіші: ключі `key_key.<name>` (напр. `key_key.forward`), значення `key.keyboard.<key>` або `key.mouse.<btn>` (напр. `key.keyboard.w`, `key.mouse.left`); старі `key_Forward` перейменовано | там само |
| Інші корисні: `lang` (`en_us`), `fov` (30–110, default 70), `guiScale` (0=auto), `maxFps`, `renderDistance`, `lastServer` | там само |
| Синтаксис рядка `ключ:значення`, по одному на рядок, без секцій — **[неперевірено за вікі]** (стаття описує ключі, але не синтаксис); загальновідомо з реальних файлів | — |
| Моди (Fabric/Forge) зазвичай додають свої `key_key.<modid>.<action>` при першому запуску — **[неперевірено]** | — |

## 7. Відкриті питання

- Чи Prism-реліз на macOS (10.x) справді робить симлінк `bin/java` — у коді так, живої перевірки нема.
- Точний ключ закріплених шляхів Java (`getPinnedPath`) у `prismlauncher.cfg`.
- Чи на поточних релізах вікі-CLI сторінка вже включає `--offline`/`--world` (станом на дослідження — ні).
