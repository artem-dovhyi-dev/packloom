# Java 17 arm64 на macOS для серверного smoke-тесту

Тікет: `issues/04-java-server-test.md`. Дата: 2026-11-05.

## Коротко

- Техпак знаходив Java не сам: `smoke-test.py` приймає шлях до `java` **аргументом** і підставляє його
  теку на початок `PATH`, а `run.sh` Forge викликає просто `java`. Останній запуск ішов з портативного
  Temurin JDK 17.0.21+9 (aarch64), який попередня сесія скачала через Adoptium API у свій scratchpad
  (`/private/tmp/claude-501/.../scratchpad/jdk/jdk-17.0.21+9/Contents/Home/bin/java`). У системі Java немає.
- Для скілу `modpack-init` рекомендую той самий підхід: **портативний Temurin tar.gz через Adoptium API у
  теку, якою володіє інструмент**, без sudo, з перевіркою sha256. Homebrew `temurin@17` простіший для людини,
  але ставить `.pkg` через `sudo installer`; Java з Prism є лише JRE від Mojang/Microsoft і залежить від
  того, чи людина вже відкривала інстанс.

## Частина A. Як це працювало в техпаку (локальні факти, нічого не змінено)

### Скрипти

- `/Users/artem/Projects/techpack/modpack/smoke-test.py`: `java = Path(sys.argv[1])`, далі
  `env = dict(os.environ, PATH=f"{java.parent}:{os.environ['PATH']}")` і `subprocess.Popen(["sh", "run.sh", "nogui"], cwd=SERVER, env=env, ...)`.
  Тобто скрипт не шукає Java і не перевіряє версію: він довіряє переданому шляху й робить так, щоб `java`
  з `run.sh` резолвилась у цю теку. Таймаут 15 хв, успіх = рядок `Done (... For help`.
- `/Users/artem/Projects/techpack/modpack/server/run.sh` (згенерований Forge installer):
  `java @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.28/unix_args.txt "$@"`.
  Жодного `JAVA_HOME`, лише `java` з `PATH`.
- `server/user_jvm_args.txt`: `-Xms2G -Xmx6G -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200`.
- `build.py` Java не торкається взагалі: `--server` лише кладе серверні jar у `server/mods`. Forge installer
  (`forge-installer.jar --installServer`) запускали окремо, руками, з тією ж Java.
- README техпаку: `python3 smoke-test.py <шлях до java 17>`; MODLIST.md: «Java: Azul Zulu або Temurin 17 для
  arm64, не x86 через Rosetta». Тікет `wayfinder/tickets/08-server-smoke-test.md` просив у людини «дозвіл
  завантажити Temurin JDK 17 arm64 і прийняти Minecraft EULA».

### Логи

- `server/install.log`, рядок 1: `JVM info: Eclipse Adoptium - 17.0.21 - 17.0.21+9`, час `04/11/2026 23:50:22`.
- `smoke-test.log`, рядок 3: `ModLauncher ... starting: java version 17.0.21 by Eclipse Adoptium; OS Mac OS X arch aarch64`.
- `server/crash-reports/crash-2026-11-04_23.58.07-fml.txt`: `Java Version: 17.0.21, Eclipse Adoptium`,
  `Java VM Version: OpenJDK 64-Bit Server VM (mixed mode, sharing)`, `Apple M1 Pro`.
- Шляхи в логах вказують, що сервер тоді жив у scratch-workspace
  `.../scratch-2026-11-04-27a689/modpack/server`, а в `Projects/techpack` його потім скопіювали.

### Де лежала Java

Системних JDK немає: `/Library/Java/JavaVirtualMachines` порожня, `~/Library/Java/JavaVirtualMachines`
відсутня, `/opt/homebrew/opt` порожня, `brew list --cask` без temurin, `/usr/libexec/java_home -V` каже
«Unable to locate a Java Runtime». Але знайшлася тека попередньої сесії:

```
/private/tmp/claude-501/-Users-artem-Library-Application-Support-Claude-scratch-workspaces-…-scratch-2026-11-04-27a689/68574e32-…/scratchpad/jdk/
  temurin17.tar.gz          186 192 554 байт, sha256 78b08c7f…1c15
  jdk-17.0.21+9/Contents/Home/bin/java
  java_path.txt             повний шлях до bin/java (його й передавали в smoke-test.py)
```

`Contents/Home/release`: `IMPLEMENTOR_VERSION="Temurin-17.0.21+9"`, `OS_ARCH="aarch64"`, `IMAGE_TYPE="JDK"`.
`bin/java -version` досі працює. Розмір розпакованого JDK + архіву 487 МБ. sha256 архіву збігається з тим,
що віддає Adoptium API (див. нижче), отже це саме офіційний `OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.21_9.tar.gz`.

Висновок: Java «знайшли» так: скачали портативний Temurin у scratchpad, зберегли шлях у `java_path.txt`,
передали цей шлях аргументом у `smoke-test.py`. Це тимчасова тека, після очищення scratchpad Java зникне,
тому для скілу потрібна стала тека.

## Частина B. Три способи отримати Java 17 arm64 (зовнішні факти)

### B1. Homebrew cask `temurin@17`

- Команда: `brew install --cask temurin@17`. У каталозі зараз версія `17.0.21,9`, артефакт
  `OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.21_9.pkg` (`brew info --cask temurin@17`, Homebrew 7.0.12 на цьому Mac).
- Джерело каска: https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/t/temurin@17.rb. Стансa
  `pkg "OpenJDK#{version.major}U-jdk_#{arch}_mac_hotspot_…pkg"`, `uninstall pkgutil: "net.temurin.17.jdk"`,
  `sha256 arm: "ab0bd83d…eb29"`. Тобто cask ставить той самий Adoptium `.pkg`, що й з сайту.
- `.pkg` Homebrew ставить через `/usr/sbin/installer -pkg … -target /` з `sudo: true, sudo_as_root: true`
  (https://github.com/Homebrew/brew/blob/HEAD/Library/Homebrew/cask/artifact/pkg.rb), тобто команда
  запитає пароль адміністратора; у неінтерактивному скрипті це блокер.
- Куди ставить: Adoptium каже, що `.pkg` кладе файли в `/Library/Java/JavaVirtualMachines/temurin-<version>.<jdk|jre>/`
  (https://adoptium.net/installation/macOS). Для цього каска це `/Library/Java/JavaVirtualMachines/temurin-17.jdk`,
  бінарник `/Library/Java/JavaVirtualMachines/temurin-17.jdk/Contents/Home/bin/java`, і він стає видимим для
  `/usr/libexec/java_home -v 17`.
- Розмір: pkg 186,6 МБ завантаження, у системі ~300 МБ. Видалення: `brew uninstall --cask temurin@17`.
- Відтворюваність: версію фіксує каталог Homebrew, а не ваш скрипт; «latest 17» міняється з оновленням каска.
  Потрібен встановлений Homebrew (на цьому Mac є).

### B2. Adoptium API, портативний tar.gz у теку інструмента

- Документація API: https://api.adoptium.net/swagger-ui і
  https://github.com/adoptium/api.adoptium.net/blob/main/docs/cookbook.adoc. Шаблон:
  `https://api.adoptium.net/v3/binary/latest/{feature_version}/ga/{os}/{arch}/{image_type}/hotspot/normal/eclipse`.
- Для нашого випадку (перевірено 2026-11-05, відповідь `307`):
  ```
  https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse
  -> https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.21%2B9/OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.21_9.tar.gz
  ```
  JSON з іменем релізу, посиланням, розміром і sha256:
  `https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse`
  (зараз віддає `jdk-17.0.21+9`, 186 192 554 байт, `78b08c7f5a0598242d5719c022e19479cb4a3aa45c37c19726a757a469ed1c15`).
  Поруч із архівом на GitHub лежить `<file>.tar.gz.sha256.txt` з тим самим хешем (cookbook, Example Three).
  Окремого `/v3/checksum/latest/...` ендпоінта немає (404).
- Розпакування за інструкцією Adoptium (https://adoptium.net/installation/archives): `tar xzf <archive>.tar.gz`,
  далі `export PATH=$PWD/<extracted_directory>/Contents/Home/bin:$PATH`; «macOS archives include a
  `Contents/Home` directory structure». Верхня тека в архіві `jdk-17.0.21+9/`.
- Без sudo, не чіпає `/Library`, не видно для `java_home`, видаляється `rm -rf` теки. Можна зафіксувати
  точну версію, замінивши `latest` на `/v3/binary/version/jdk-17.0.21%2B9/mac/aarch64/jdk/hotspot/normal/eclipse`.
- Якщо потрібен менший слід: `image_type=jre` замість `jdk` (для Forge-сервера JRE достатньо, але JDK
  зручніший для `jar`/`jcmd`; різниця ~100 МБ).

### B3. Java, яку вже скачав Prism Launcher

- Prism 9.0+ вміє «Auto-download Mojang Java» (https://prismlauncher.org/wiki/getting-started/installing-java/);
  де саме зберігає, вікі не каже. На цьому Mac факт такий:
  ```
  ~/Library/Application Support/PrismLauncher/java/java-runtime-gamma/bin/java
    -> …/java-runtime-gamma/jre.bundle/Contents/Home/bin/java   (Mach-O arm64)
  ```
  `release`: `JAVA_VERSION="17.0.15"`, `java -version`: `OpenJDK Runtime Environment Microsoft-11369864 (build 17.0.15+6-LTS)`,
  розмір 92 МБ (це JRE, не JDK). Інстанс `instances/TechPack-1.0.0/instance.cfg` має
  `JavaPath=/Users/artem/Library/Application Support/PrismLauncher/java/java-runtime-gamma/bin/java`.
- Джерело цих рантаймів: `meta/net.minecraft.java/java17.json`, записи `runtimeOS: mac-os-arm64`,
  `vendor: mojang`, `packageType: jre`, маніфест `piston-meta.mojang.com/.../e0c8d5cc…/manifest.json`
  (той самий runtime, що й у офіційному лаунчері; ім'я теки `java-runtime-gamma` = компонент Mojang для 1.18-1.20.4).
- Шаблон шляху: `~/Library/Application Support/PrismLauncher/java/<runtime-name>/bin/java`, де
  `<runtime-name>` для MC 1.20.1 = `java-runtime-gamma`.
- Обмеження: тека з'являється тільки після того, як людина імпортувала інстанс і хоча б раз його запустила
  з увімкненим авто-завантаженням; версія (17.0.15) відстає від Temurin (17.0.21) і залежить від Mojang;
  Prism може прибрати/оновити теку сам. Для скрипта це приємний fallback, а не основа.

## Порівняння

| Критерій | Homebrew `temurin@17` | Adoptium API tar.gz | Prism `java-runtime-gamma` |
|---|---|---|---|
| Команда | `brew install --cask temurin@17` | `curl` + `tar` (нижче) | нічого, лише перевірити шлях |
| sudo | так (pkg через `installer`) | ні | ні |
| Слід у системі | `/Library/Java/JavaVirtualMachines/temurin-17.jdk`, ~300 МБ, видно для `java_home` | лише тека інструмента, ~300 МБ JDK (або ~100 МБ JRE) | 92 МБ, уже є, ним володіє Prism |
| Фіксація версії | версію диктує каталог Homebrew | можна зафіксувати `jdk-17.0.21+9` і sha256 | 17.0.15 від Mojang, не керуємо |
| Відтворюваність у скрипті | потрібен Homebrew і пароль | одна залежність: `curl` | працює тільки якщо інстанс уже запускали |
| Видалення | `brew uninstall --cask temurin@17` | `rm -rf` теки | не чіпати |

## Рекомендація для `modpack-init`

Основний шлях: портативний Temurin через Adoptium API у теку скіла, напр. `~/.cache/modpack-init/jdk17`
(або `<repo>/.tools/jdk17`, доданий у `.gitignore`). Без sudo, детермінований, видно хеш.

```sh
JDK_DIR="${MODPACK_JDK_DIR:-$HOME/.cache/modpack-init/jdk17}"
if [ ! -x "$JDK_DIR/Contents/Home/bin/java" ]; then
  mkdir -p "$JDK_DIR.dl" && cd "$JDK_DIR.dl"
  URL="https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse"
  FETCH_URL=$(curl -s -w '%{redirect_url}' "$URL")                   # 307 -> github release asset
  curl -LsS -o temurin17.tar.gz "$FETCH_URL"
  curl -LsS "$FETCH_URL.sha256.txt" | sed 's/  .*/  temurin17.tar.gz/' | shasum -a 256 -c -
  tar xzf temurin17.tar.gz                                           # створює jdk-17.0.21+9/
  mv jdk-17.* "$JDK_DIR" && cd .. && rm -rf "$JDK_DIR.dl"
fi
JAVA="$JDK_DIR/Contents/Home/bin/java"
"$JAVA" -version                                                     # очікуємо Temurin-17.0.x, aarch64
python3 smoke-test.py "$JAVA"
```

Примітки до скрипта:

- Якщо скіл хоче повної фіксації, замінити `latest/17/ga` на `version/jdk-17.0.21%2B9` і вшити sha256
  `78b08c7f5a0598242d5719c022e19479cb4a3aa45c37c19726a757a469ed1c15`.
- Порядок пошуку перед завантаженням (щоб не качати зайве): 1) `$JDK_DIR`; 2) `/usr/libexec/java_home -v 17`
  (знайде Homebrew/Adoptium `.pkg`, якщо людина вже ставила); 3) `~/Library/Application Support/PrismLauncher/java/java-runtime-gamma/bin/java`
  як fallback з перевіркою `java -version | grep '"17\.'`. Лише потім Adoptium API.
- Для Forge installer та `run.sh` достатньо, щоб `$JAVA` був виконуваним; `smoke-test.py` сам підставить його
  теку в `PATH`. `run.sh` сам по собі шукає `java` у `PATH`, тому для ручного запуску:
  `PATH="$(dirname "$JAVA"):$PATH" sh run.sh nogui`.
- Homebrew залишити як варіант «для людини» в документації (`brew install --cask temurin@17`, потім
  `/usr/libexec/java_home -v 17`), але не викликати з агента: запит пароля зламає неінтерактивний прогін.
- Запуск скачаного JDK з тимчасової теки, як було в техпаку, повторювати не варто: Java зникла б разом зі
  scratchpad, і `java_path.txt` став би недійсним.

## Джерела

- Локальні: `/Users/artem/Projects/techpack/modpack/{smoke-test.py,build.py,README.md,MODLIST.md,smoke-test.log}`,
  `server/{run.sh,user_jvm_args.txt,install.log,crash-reports/crash-2026-11-04_23.58.07-fml.txt}`,
  `wayfinder/tickets/08-server-smoke-test.md`; тека попередньої сесії `/private/tmp/claude-501/…-scratch-2026-11-04-27a689/…/scratchpad/jdk/`;
  `~/Library/Application Support/PrismLauncher/{prismlauncher.cfg,java/,meta/net.minecraft.java/java17.json,instances/TechPack-1.0.0/instance.cfg}`.
- Adoptium, встановлення на macOS: https://adoptium.net/installation/macOS
- Adoptium, архіви tar.gz: https://adoptium.net/installation/archives
- Adoptium API cookbook: https://github.com/adoptium/api.adoptium.net/blob/main/docs/cookbook.adoc; Swagger: https://api.adoptium.net/swagger-ui
- Живі відповіді API (2026-11-05): https://api.adoptium.net/v3/binary/latest/17/ga/mac/aarch64/jdk/hotspot/normal/eclipse,
  https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=aarch64&image_type=jdk&os=mac&vendor=eclipse
- Homebrew cask: https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/t/temurin@17.rb
- Homebrew pkg artifact (sudo installer): https://github.com/Homebrew/brew/blob/HEAD/Library/Homebrew/cask/artifact/pkg.rb
- Homebrew Cask Cookbook, стансa `pkg`: https://docs.brew.sh/Cask-Cookbook
- Prism Launcher, Java: https://prismlauncher.org/wiki/getting-started/installing-java/
