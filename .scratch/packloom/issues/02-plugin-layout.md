# Структура плагіна Claude Code і як techpack його підключає

Type: research
Status: resolved
Blocked by:

## Question

Як влаштовано плагін Claude Code у 2026: маніфест, папки skills/, agents/, hooks/, scripts, як скіл викликає
Python-скрипт із плагіна (шлях до базової папки скіла, змінні оточення), як встановити плагін з локальної
папки або git-репозиторію без маркетплейсу, і чи може проєкт (techpack) закріпити плагін у своїх налаштуваннях.
Результат: факти з посиланнями на документацію, рекомендована структура репозиторію packloom і спосіб
підключення для techpack. Спитати агента claude-code-guide, не вгадувати.

## Answer

Плагін = папка з `.claude-plugin/plugin.json` (обов'язкове лише `name`) і стандартними папками `skills/<name>/SKILL.md`,
`agents/`, `hooks/hooks.json`; `commands/` — старий формат, `scripts/` — лише конвенція. Скіл викликає бандлений
скрипт через `python3 ${CLAUDE_SKILL_DIR}/scripts/x.py` (підставляється в тілі SKILL.md і в `allowed-tools`), спільний
код — через `${CLAUDE_PLUGIN_ROOT}/lib`; ці змінні не є в оточенні Bash, Python-залежності не ставляться автоматично
(venv у `${CLAUDE_PLUGIN_DATA}` через SessionStart-хук). Front-matter скіла: `name`, `description`, `when_to_use`,
`allowed-tools`, `user-invocable`, `disable-model-invocation`, `context: fork`, `model`, `effort`, `paths`, `hooks`.
Без маркетплейсу — тільки `claude --plugin-dir <path>` (на сесію, in-place); `claude plugin install` вимагає
маркетплейс, але репо packloom може бути своїм маркетплейсом (`marketplace.json` з `"source": "./"`).
techpack закріплює плагін у `.claude/settings.json`: `extraKnownMarketplaces.packloom` (github, `ref`) +
`enabledPlugins["packloom@packloom"]: true`; для relative-path плагіна колаборатору не треба `plugin install`,
лише довірити папку. Розробка — `--plugin-dir /Users/artem/Projects/packloom`, він перекриває маркетплейсний.
Деталі, структура репо і джерела: [research/02-plugin-layout.md](../research/02-plugin-layout.md).
