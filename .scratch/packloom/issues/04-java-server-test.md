# Java 17 для серверного тесту на macOS arm64 і як smoke-test.py її знаходить зараз

Type: research
Status: resolved
Blocked by:

## Question

Який найпростіший відтворюваний спосіб отримати Java 17 arm64 на macOS для серверного тесту (Temurin через
Homebrew, завантаження в папку плагіна, чи Java з Prism), і як саме techpack/modpack/smoke-test.py та
server/install.log знаходили Java під час останнього запуску (на Mac зараз немає Java runtime, але лог є).
Результат: рекомендований спосіб для скілу modpack-init з командами, і факт про те, як це працювало в техпаку.
Прочитати smoke-test.py, build.py, server/install.log у /Users/artem/Projects/techpack/modpack, нічого там не змінювати.

## Answer

- У техпаку Java не шукали: `smoke-test.py` бере шлях до `java` аргументом і підставляє його теку в `PATH`,
  а `server/run.sh` Forge викликає просто `java`. `build.py` Java не торкається.
- Останній прогін (install.log: `JVM info: Eclipse Adoptium - 17.0.21 - 17.0.21+9`, smoke-test.log: `aarch64`)
  ішов з портативного Temurin tar.gz, який попередня сесія скачала через Adoptium API у свій scratchpad
  (`/private/tmp/claude-501/…-scratch-2026-11-04-27a689/…/scratchpad/jdk/jdk-17.0.21+9/Contents/Home/bin/java`,
  шлях збережено в `java_path.txt`). Системних JDK на Mac немає, Homebrew temurin не ставили.
- Рекомендація для `modpack-init`: той самий підхід, але в сталу теку (`~/.cache/modpack-init/jdk17`):
  `curl -s -w '%{redirect_url}' https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse`,
  скачати, звірити `<file>.sha256.txt`, `tar xzf`, java = `<dir>/Contents/Home/bin/java`. Без sudo, версію можна зафіксувати.
- Homebrew `brew install --cask temurin@17` ставить той самий `.pkg` у `/Library/Java/JavaVirtualMachines/temurin-17.jdk`,
  але через `sudo installer` (запит пароля), тож лишити як варіант для людини, не для агента.
- Prism уже має arm64 JRE 17.0.15 (Microsoft, від Mojang) у `~/Library/Application Support/PrismLauncher/java/java-runtime-gamma/bin/java`;
  годиться як fallback, якщо інстанс уже запускали, але версією не керуємо.
- Повні факти, порівняння і готовий фрагмент скрипта: `research/04-java-server-test.md`.
