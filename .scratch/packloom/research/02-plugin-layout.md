# Структура плагіна Claude Code (2026) і підключення packloom до techpack

Дата: 2026-11-05. Джерела: офіційна документація Claude Code (code.claude.com/docs), перевірена через агента
`claude-code-guide` і прямим читанням сторінок. Де документація мовчить, це сказано явно.

## 1. Факти

### 1.1. Маніфест `.claude-plugin/plugin.json`

- Лежить у `<корінь плагіна>/.claude-plugin/plugin.json`. Усе інше (skills/, hooks/, scripts/) лежить у корені
  плагіна, а не всередині `.claude-plugin/`.
- Маніфест необов'язковий: без нього Claude Code завантажує компоненти зі стандартної розкладки. Єдине
  обов'язкове поле, якщо маніфест є, це `name` (kebab-case; без пробілів, `@`, `:`, слешів). Усі компоненти
  неймспейсяться під ним: `/packloom:build`, агент `packloom:reviewer`.
- Поля верхнього рівня: `$schema`, `name`, `displayName`, `version`, `description`, `author` {name, email, url},
  `homepage`, `repository`, `license` (SPDX), `keywords`, `metadata`, `defaultEnabled`, `dependencies`,
  `settings` (діють лише `agent` і `subagentStatusLine`), `userConfig`, `channels`, `skills`, `commands`,
  `agents`, `hooks`, `mcpServers`, `lspServers`, `outputStyles`, `workflows`, `experimental` {themes, monitors,
  evals}, плюс поля для каталогу Anthropic (`icon`, `documentationUrl`, ...), які Claude Code ігнорує.
- Невідоме поле верхнього рівня відкидається з попередженням від `claude plugin validate <path>`; невідомий
  ключ усередині `userConfig`/`channels`/`lspServers`/`monitors` є помилкою і плагін не завантажується.
- `version`: рядок, не перевіряється на semver. Якщо задано, користувачі лишаються на цій версії, поки автор
  не змінить рядок (кеш не оновлюється на нові коміти). Якщо не задано, версія береться з commit SHA (12 символів).
  На плагін, завантажений in-place з локального маркетплейсу, `version` не впливає.
- Джерело: https://code.claude.com/docs/en/plugins/manifest-reference.md

### 1.2. Стандартна розкладка і правила шляхів

| Компонент | Де за замовчуванням |
| --- | --- |
| Маніфест | `.claude-plugin/plugin.json` |
| Скіли | `skills/<name>/SKILL.md` (один SKILL.md у корені без `skills/` теж працює як один скіл) |
| Команди | `commands/*.md` — старий формат, "Prefer skills/ for new plugins" |
| Агенти | `agents/*.md` (підпапки входять в імʼя: `agents/review/security.md` → `plugin:review:security`) |
| Хуки | `hooks/hooks.json` (з обгорткою `"hooks": {...}`) |
| MCP | `.mcp.json`; LSP: `.lsp.json` |
| Виконувані файли | `bin/` — додаються в PATH Bash-інструмента, поки плагін увімкнений |
| Інше | `scripts/` — це лише конвенція: "The name `scripts/` is a convention, not something Claude Code looks for" |

- Будь-який шлях у маніфесті має починатися з `./` (`commands/foo.md` не проходить валідацію); виняток:
  `skills` приймає також `"."`.
- `commands`, `agents`, `outputStyles`, `workflows` у маніфесті ЗАМІНЮЮТЬ сканування папки за замовчуванням;
  `skills` ДОДАЄ до `skills/`; `hooks`, `mcpServers`, `lspServers` ЗЛИВАЮТЬСЯ з файлом за замовчуванням.
- Шлях, що виходить за корінь плагіна (`../shared`), відкидається: `path escapes plugin directory`. Під час
  копіювання в кеш файли поза коренем плагіна не копіюються.
- `CLAUDE.md` у корені плагіна НЕ завантажується як контекст (validate попереджає). Інструкції кладуть у скіл.
- Джерела: https://code.claude.com/docs/en/plugins/manifest-reference.md#standard-layout ,
  https://code.claude.com/docs/en/plugins/components.md

### 1.3. Як скіл викликає бандлений скрипт: змінні шляхів

| Змінна | Значення |
| --- | --- |
| `${CLAUDE_SKILL_DIR}` | Папка, де лежить SKILL.md цього скіла. Для плагінного скіла це підпапка в плагіні, не корінь плагіна |
| `${CLAUDE_PLUGIN_ROOT}` | Абсолютний шлях до встановленої версії плагіна (`~/.claude/plugins/cache/<market>/<plugin>/<version>/`; для in-place плагінів — вихідна папка). Змінюється з кожною версією, стан туди не писати |
| `${CLAUDE_PLUGIN_DATA}` | `~/.claude/plugins/data/<id>/` — переживає оновлення; для `node_modules`, venv, кешів |
| `${CLAUDE_PROJECT_DIR}` | Корінь проєкту (поточна сесія) |

- У тілі SKILL.md (і в правилах `Bash(...)` у `allowed-tools`) підставляються `${CLAUDE_SKILL_DIR}`,
  `${CLAUDE_PROJECT_DIR}`, а в плагінному скілі ще `${CLAUDE_PLUGIN_ROOT}` і `${CLAUDE_PLUGIN_DATA}`.
  Підстановка відбувається, коли Claude Code завантажує вміст скіла, тобто модель бачить уже абсолютний шлях.
- Ці змінні НЕ присутні в оточенні команд, які Claude запускає через Bash tool. Тому шлях треба писати в
  Markdown, а не покладатися на `$CLAUDE_PLUGIN_ROOT` у shell. В оточення вони експортуються тільки для хуків,
  MCP stdio і LSP процесів.
- Документований приклад (skills.md):

```yaml
---
name: render-chart
description: Render a chart from a CSV file
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)
---
Run `${CLAUDE_SKILL_DIR}/scripts/render.sh <csv-file>` to render the chart.
```

  Той самий патерн для Python: `python3 ${CLAUDE_SKILL_DIR}/scripts/visualize.py .` з `allowed-tools: Bash(python3 *)`.
- Чи повідомляє Claude Code моделі базову папку скіла окремим рядком: у документації НЕ описано. Спостережено в
  цій сесії: виклик Skill-інструмента повертає рядок `Base directory for this skill: <абсолютний шлях>` перед
  тілом скіла. Покладатися на це не варто; надійний шлях — `${CLAUDE_SKILL_DIR}` у тексті.
- Python-залежності НЕ встановлюються автоматично (автоінсталяція є лише для npm/bun lockfile). Документований
  шлях: хук `SessionStart`, що ставить залежності (venv) у `${CLAUDE_PLUGIN_DATA}`. Для скриптів без вимоги
  "executable" немає: запуск через інтерпретатор (`python3 ...`) — документований патерн; для `bin/` і
  shell-хуків треба `chmod +x`.
- Джерела: https://code.claude.com/docs/en/skills.md (таблиця Variables),
  https://code.claude.com/docs/en/plugins/manifest-reference.md#environment-variables ,
  https://code.claude.com/docs/en/plugins/components.md#reference-plugin-paths-and-store-data ,
  https://code.claude.com/docs/en/plugins/loading.md#node-js-package-dependencies

### 1.4. Front-matter SKILL.md

Усі поля необов'язкові, рекомендовано лише `description`. Невідомі поля ігноруються.

| Поле | Семантика |
| --- | --- |
| `name` | Імʼя команди в меню `/`. За замовчуванням — імʼя папки. У плагіні замінює останній сегмент: `skills/review/` + `name: fancy` → `/my-plugin:fancy` |
| `description` | Що робить і коли застосовувати; за ним Claude вирішує, чи підвантажити скіл. Разом із `when_to_use` обрізається до 1 536 символів у списку скілів |
| `when_to_use` | Тригерні фрази; дописується до description |
| `argument-hint` | Підказка аргументів в автодоповненні, напр. `[mod-slug]` |
| `arguments` | Іменовані аргументи для підстановки `$name` |
| `disable-model-invocation` | `true` — тільки користувач через `/name`; також не прелоадиться в сабагентів |
| `user-invocable` | `false` — тільки Claude; схований з меню `/` |
| `allowed-tools` | Інструменти без запиту дозволу на хід, у якому викликано скіл (рядок або YAML-список) |
| `disallowed-tools` | Заборонені інструменти |
| `model`, `effort` | На решту поточного ходу (або для форкнутого сабагента при `context: fork`) |
| `context: fork`, `agent`, `background` | Виконати скіл у форкнутому сабагенті; `agent` — тип сабагента |
| `hooks` | Хуки, що реєструються при виклику скіла на решту сесії |
| `paths` | Glob-патерни відносно cwd: скіл автопідвантажується тільки при роботі з такими файлами |
| `shell` | `bash` (default) або `powershell` |
| `metadata`, `license`, `compatibility` | Поля специфікації Agent Skills |

- Неймспейс у плагіні: `/<plugin>:<skill>`. Плагінний скіл і однойменний локальний скіл не конфліктують.
- Рекомендовано тримати SKILL.md до 500 рядків; допоміжні файли (references, scripts) у папці скіла.
- Джерело: https://code.claude.com/docs/en/skills.md

### 1.5. Агенти в плагіні (`agents/*.md`)

- Обов'язкові: `name` (до 256 символів, без `:`) і `description`.
- Підтримувані в плагіні: `model`, `effort`, `maxTurns`, `autoCompactWindow`, `tools`, `disallowedTools`,
  `skills`, `memory`, `background`, `omitClaudeMd`, `isolation: worktree`, `color`, `experimental.cacheTtl`.
- Ігноруються в плагінних агентах з міркувань безпеки: `permissionMode`, `hooks`, `mcpServers`, `initialPrompt`.
- Виклик: `@agent-packloom:<name>`.
- Джерела: https://code.claude.com/docs/en/plugins/components.md#agents , https://code.claude.com/docs/en/sub-agents.md

### 1.6. Встановлення без маркетплейсу і з власним маркетплейсом

- **`claude --plugin-dir <path>`** — на одну сесію, не персистентно; прапор повторюваний; приймає папку або
  `.zip`; плагін видно як `<name>@inline`. Завантажується in-place, без копіювання. Є ще `--plugin-url` і змінна
  `CLAUDE_CODE_PLUGIN_DIRS`. Це документований спосіб для розробника тестувати локальну копію.
- **`claude plugin install <name>@<marketplace>`** ставить ТІЛЬКИ з маркетплейсу. Команди `claude plugin add`
  не існує (є `install`, alias `i`). Встановлення з "голого" шляху чи git URL без marketplace.json не
  документовано.
- **Маркетплейс може бути чим завгодно**: GitHub `owner/repo` (з `#ref`), будь-який git URL, локальна папка
  (`./path`, обов'язково з `./` або `../`, бо `a/b` читається як GitHub) або сам `.json`. Додається через
  `claude plugin marketplace add <source>` або `/plugin marketplace add <source>`. Є скорочення "додати і
  встановити": `claude plugin install packloom --marketplace owner/repo` (v2.1.292+).
- **Репозиторій може бути одночасно плагіном і своїм маркетплейсом**: `.claude-plugin/marketplace.json` з
  записом `"source": "./"` (документовано в розділі про submodules: "A plugin at the marketplace root, with
  `"source": "./"`"). Обов'язкові ключі marketplace.json: `name`, `owner.name`, `plugins[]` з `name` і `source`.
  Відносні шляхи починаються з `./`, `"."` означає корінь.
- Плагіни з маркетплейсу, доданого з ЛОКАЛЬНОЇ папки, завантажуються in-place: правки в джерелі діють після
  `/reload-plugins` або нової сесії, версію піднімати не треба. З git-маркетплейсу плагін копіюється в
  `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.
- Ще один шлях без маркетплейсу: папка плагіна (з `.claude-plugin/plugin.json`) усередині `~/.claude/skills/`
  або `<проєкт>/.claude/skills/` завантажується як `<name>@skills-dir`. Папку `.claude/plugins/` проєкту
  Claude Code НЕ сканує.
- Пінінг версій: `version` у plugin.json (пін до зміни рядка), `ref`/`sha` у джерелах `github`/`url`/
  `git-subdir` (40-символьний SHA має пріоритет над ref), `sha256` для `archive`.
- Джерела: https://code.claude.com/docs/en/plugins/cli-reference.md ,
  https://code.claude.com/docs/en/plugins/install.md#add-a-marketplace ,
  https://code.claude.com/docs/en/plugins/marketplace-reference.md ,
  https://code.claude.com/docs/en/plugins/loading.md#in-place-and-copied-plugins

### 1.7. Чи може проєкт закріпити плагін у `.claude/settings.json`

Так. Документований механізм "Require plugins per repository":

```json
{
  "extraKnownMarketplaces": {
    "packloom": {
      "source": { "source": "github", "repo": "<owner>/packloom" }
    }
  },
  "enabledPlugins": {
    "packloom@packloom": true
  }
}
```

- Ключ `enabledPlugins` має форму `<entry-name>@<marketplace-name>`, значення boolean. Імʼя плагіна — це
  `name` запису в marketplace.json; імʼя маркетплейсу — `name` у marketplace.json (воно ж ключ в
  `extraKnownMarketplaces`).
- `extraKnownMarketplaces` з репозиторію діє лише після того, як користувач довірив папку (workspace trust
  dialog); у недовіреній папці ігнорується мовчки. У хмарних сесіях (claude.ai/code) репозиторні
  маркетплейси не додаються взагалі.
- Ключова відмінність для relative-path плагінів: "A plugin that the marketplace lists by a relative path
  loads from the marketplace copy once the repository's `extraKnownMarketplaces` entries apply" і "A
  relative-path plugin needs no install record because it loads from the marketplace itself". Тобто якщо
  packloom-репо є своїм маркетплейсом з `"source": "./"`, колаборатору techpack НЕ треба запускати
  `claude plugin install` — достатньо довірити папку. Якщо ж запис маркетплейсу вказує на зовнішнє джерело
  (окремий github-репо плагіна), кожен колаборатор бачить `Plugin "<name>" is enabled in project settings but
  isn't installed here` і мусить один раз виконати `claude plugin install packloom@packloom --scope project`.
- Пріоритет `enabledPlugins` (від нижчого): `--add-dir` → user (`~/.claude/settings.json`) → project
  (`.claude/settings.json`) → local (`.claude/settings.local.json`) → `--settings` → managed. Вимкнути
  проєктний плагін для себе: `"packloom@packloom": false` у `.claude/settings.local.json`.
- Автооновлення для неофіційних маркетплейсів за замовчуванням вимкнене; можна задати `"autoUpdate": true` в
  записі `extraKnownMarketplaces`.
- Project-scope плагін проходить trust check; його `.mcpb`-бандли і monitors не вантажаться (скілів, хуків,
  inline MCP це не стосується).
- Джерела: https://code.claude.com/docs/en/plugins/org.md#require-plugins-per-repository ,
  https://code.claude.com/docs/en/plugins/loading.md#enabled-in-project-settings-but-not-installed ,
  https://code.claude.com/docs/en/plugins/install.md#choose-an-install-scope

### 1.8. CLI `claude plugin ...` (стисло)

`init|new`, `install|i` (`--scope user|project|local`, `--marketplace <source>`, `-y`), `uninstall|rm`,
`enable`, `disable`, `update`, `list`, `details <name>`, `configure`, `prune`, `validate <path> [--strict]`,
`tag`, `eval`, `test`, `marketplace add|list|update|remove`. У сесії: `/plugin ...`, `/reload-plugins [--force]`.
Джерело: https://code.claude.com/docs/en/plugins/cli-reference.md

## 2. Рекомендована структура репозиторію packloom

```text
packloom/                         # git-репо = плагін = власний маркетплейс
├── .claude-plugin/
│   ├── plugin.json                 # { "name": "packloom", "description": ..., "author": ..., "license": "MIT" }
│   └── marketplace.json            # { "name": "packloom", "owner": {"name": "Artem"},
│                                   #   "plugins": [{ "name": "packloom", "source": "./" }] }
├── skills/
│   ├── pack-build/
│   │   ├── SKILL.md                # name/description/allowed-tools; викликає scripts через ${CLAUDE_SKILL_DIR}
│   │   ├── scripts/build.py        # тонкий CLI-вхід; імпортує спільний код із lib/
│   │   └── reference.md            # синтаксис опису збірки (підвантажується на вимогу)
│   ├── pack-smoke-test/
│   │   ├── SKILL.md
│   │   └── scripts/smoke_test.py
│   ├── pack-keybinds/
│   │   └── ...
│   └── packloom/                 # user-invocable: false — довідка про домен для Claude, не для меню
│       └── SKILL.md
├── lib/packloom/                 # спільний Python-пакет (парсер опису збірки, завантажувач модів, ...)
│   └── __init__.py
├── agents/                         # за потреби, напр. reviewer збірки
├── hooks/hooks.json                # за потреби: SessionStart → venv у ${CLAUDE_PLUGIN_DATA}
├── tests/                          # pytest для lib/ і scripts/ (не читається Claude Code)
├── README.md                       # англійською; CLAUDE.md у корені плагіна НЕ вантажиться
└── LICENSE
```

Правила, що з цього випливають:

1. **Скрипти викликаються через змінні, не відносні шляхи.** У SKILL.md: `python3 ${CLAUDE_SKILL_DIR}/scripts/build.py --pack ${CLAUDE_PROJECT_DIR}/modpack`;
   спільна бібліотека підключається у скрипті через `sys.path.insert(0, Path(__file__).resolve().parents[3] / "lib")`
   або через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}/lib python3 ...` у тій самій команді. Шлях `${CLAUDE_PLUGIN_ROOT}`
   змінюється між версіями, тому нічого не кешувати в ньому.
2. **Без дозволів на кожен запуск**: у front-matter `allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)`
   — правило й команда в тілі розкриваються в один і той самий абсолютний шлях.
3. **Залежності**: перший зріз — тільки stdlib (urllib, json, zipfile, tomllib). Якщо з'являться пакети
   (`requests`, `tomlkit`), додати `hooks/hooks.json` з `SessionStart`-хуком, що створює venv у
   `${CLAUDE_PLUGIN_DATA}/venv` і ставить `requirements.txt`; скіли тоді запускають
   `${CLAUDE_PLUGIN_DATA}/venv/bin/python`. Автоінсталяції для Python нема.
4. **Дані збірки лишаються в проєкті** (`${CLAUDE_PROJECT_DIR}/modpack/...`), плагін — лише код і довідки.
   Це та сама межа "загальний код / дані збірки", що вже прийнята в issue 01.
5. **`version` у plugin.json не задавати**, поки йде активна розробка: тоді версія = commit SHA і `claude plugin
   update` підтягує кожен коміт. Задати `version` лише для релізів друзям/публіці.
6. `commands/` не створювати — старий формат. `bin/` не потрібен (і він блокує встановлення на claude.ai/Cowork).

## 3. Як techpack підключає плагін

Три режими, від розробки до публіки:

**A. Розробка (зараз).** Локальний клон `/Users/artem/Projects/packloom`. Запускати з techpack
`claude --plugin-dir /Users/artem/Projects/packloom` (або задати `CLAUDE_CODE_PLUGIN_DIRS` в оточенні, щоб
не писати прапор щоразу). Плагін вантажиться in-place як `packloom@inline`; правки видно після
`/reload-plugins`. Це документований шлях для автора плагіна, і він має пріоритет над однойменним плагіном з
маркетплейсу, тож режим B у тому ж репо не заважає. Локальний маркетплейс (`claude plugin marketplace add
./../packloom`) теж працює in-place, але його `name` збігатиметься з github-маркетплейсом із режиму B, а два
маркетплейси з одним імʼям не реєструються, тому для розробки краще `--plugin-dir`.

**B. Закріплення в репо techpack (для друзів).** У `/Users/artem/Projects/techpack/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "packloom": {
      "source": { "source": "github", "repo": "<owner>/packloom", "ref": "main" }
    }
  },
  "enabledPlugins": { "packloom@packloom": true }
}
```

Оскільки запис маркетплейсу для packloom має relative-path джерело `"./"`, плагін завантажується з копії
маркетплейсу без `claude plugin install` на боці колаборатора — йому досить довірити папку techpack. Для
пінінгу на стабільний стан замінити `ref` на тег (`"ref": "v0.1.0"`); поле `sha` є лише в plugin-джерелах, не в marketplace-джерелах. Артем локально перекриває це своїм клоном через `--plugin-dir` з режиму A: inline-плагін мовчки
замінює однойменний плагін з маркетплейсу (loading.md, Name conflicts).

**C. Публіка.** Те саме, що B, плюс `README` з командою
`claude plugin install packloom --marketplace <owner>/packloom` (додає маркетплейс і ставить у user scope
одним рядком) і теги релізів через `claude plugin tag`.

Обмеження, які варто пам'ятати: хмарні сесії claude.ai/code не підхоплюють репозиторні маркетплейси; project-scope
плагін вантажиться лише після trust dialog; `extraKnownMarketplaces` з локальним `directory`-джерелом у репо
резолвиться відносно головного checkout, тож worktree-и ділять одну папку.
