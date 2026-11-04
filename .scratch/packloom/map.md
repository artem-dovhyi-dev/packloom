# Карта: packloom (wayfinder:map)

Трекер: локальний markdown. Тікети в `issues/NN-slug.md` з рядками `Type:`, `Status:` (open/claimed/resolved),
`Blocked by:`. Фронтир = open, без claim, усі Blocked by resolved. Відповідь пишеться в `## Answer` тікета,
дослідження лежать у `research/`.

## Destination

Специфікація плагіна packloom для Claude Code, достатньо різка, щоб почати перший зріз: структура плагіна,
межа між загальним кодом і даними збірки, синтаксис опису збірки, контракт циклу перевірки через серверний тест,
і форма прототипу клавіатури. Після мапи лишається тільки реалізація зрізів.

## Notes

- Домен: редактор Minecraft-збірок як скіли для Claude Code, Python-скрипти, без MCP і без лаунчера.
- Перший споживач: `/Users/artem/Projects/techpack/modpack` (1.20.1 Forge, mods.txt, build.py, smoke-test.py,
  quests/gen_quests.py, overrides/). Його мапа: `wayfinder/MAP.md` у тій папці.
- Стандартна перевага Артема: не питати раундами, а пропонувати і обирати. HITL-тікети вирішуються
  рекомендацією агента з явними припущеннями, Артем править потім. Один тікет за сесію лишається в силі.
- Мова документів і тікетів: українська. Код і README репозиторію: англійська.
- Скіли для сесій: `mattpocock-skills:research`, `mattpocock-skills:prototype`, `mattpocock-skills:grilling`,
  `mattpocock-skills:domain-modeling`. Для структури плагіна питати агента `claude-code-guide`.
- Для себе, потім друзі, потім публіка; паралельно це шоукейс для резюме.
- Режим з 2026-11-05 ночі: Артем дозволив виконання в межах мапи без питань («рубай протягом ночі, рішення приймаю сам»). Один тікет за сесію не діє; HITL-тікети закриваються рішенням агента з припущеннями.
- Стан середовища 2026-11-05 01:12: Prism встановлено, інстанс `~/Library/Application Support/PrismLauncher/instances/TechPack-1.0.0/minecraft` імпортовано, 83 моди, Java 17.0.15 від Prism; гра до меню ще не доходила (logs/ відсутній, options.txt порожній).

## Decisions so far

- [Базові рішення з ґрилінг-сесії](issues/01-base-decisions.md): окремий публічний плагін, Python, 1.20.1 Forge,
  свій build.py замість Packwiz, серверний smoke-тест як цикл, Java-моди поза скоупом, порядок зрізів.
- [Java 17 для серверного тесту](issues/04-java-server-test.md): портативний Temurin через Adoptium API у `~/.cache/modpack-init/jdk17`, без sudo; порядок пошуку: своя тека → java_home → Prism → Adoptium. Техпак Java не шукав, брав шлях аргументом.
- [Структура плагіна Claude Code](issues/02-plugin-layout.md): `.claude-plugin/plugin.json` + `skills/<name>/SKILL.md` зі скриптами через `${CLAUDE_SKILL_DIR}/scripts/*.py`, спільний код у `lib/`; репозиторій сам собі маркетплейс (`marketplace.json`), techpack підключає через `extraKnownMarketplaces` + `enabledPlugins` у `.claude/settings.json`; для розробки `claude --plugin-dir`.
- [Prism Launcher на macOS](issues/03-prism-layout.md): інстанси в `~/Library/Application Support/PrismLauncher/instances/<id>/minecraft/` (mods, config, options.txt, logs/latest.log, crash-reports); версія і лоадер у `mmc-pack.json`, Java і пам'ять в `instance.cfg`; CLI `-l <id>`, `-I <mrpack>`, але без headless і без запуску без акаунта, тож серверний тест лишається єдиним автоматичним циклом.
- [Назва і README](issues/10-name-and-readme.md): packloom (packwright зайнята); README-абзац і рядок для резюме в тікеті.
- [Межа плагін/дані](issues/05-generic-vs-specific.md): build і smoke у плагін з pack.json, квести і реєстр поки лишаються в techpack; старі скрипти живуть до першої ідентичної збірки.
- [Синтаксис mods.txt і pack.json](issues/06-pack-manifest-syntax.md): голий слаг, `slug@ver`, `slug client|server`, `ftb:`, `url:`, `manual:`; старий файл валідний без змін.
- [Контракт перевірки](issues/07-verification-contract.md): `smoke-report.json` із suspects за евристиками; triage пропонує, build застосовує; EULA лише з явним прапором.
- [Перший клієнтський запуск](issues/09-install-prism-first-launch.md): зроблено Артемом; 143 бінди, лог без крашів, клієнтський triage ok.
- [Прототип клавіатури](issues/08-keyboard-prototype.md): `packloom keys` → keybinds.html; на техпаку 16 жорстких конфліктів; евристика modid потребує синонімів.

## Стан

2026-11-05 ніч: зріз 1 виконано (репозиторій `~/Projects/packloom`, плагін збирає techpack ідентично до старого build.py). Серверний тест через плагін: OK за 24 с. Зріз 2 (клавіатура) зроблено як прототип. Усі 10 тікетів закриті; фронтир порожній, далі лише туман нижче.

## Not yet specified

- HTML-шпаргалка збірки: що на ній, як генерується, де хоститься (GitHub Pages?). Чекає на форму клавіатури.
- Запис розкладки клавіш назад в options.txt після перегляду у прототипі; таблиця синонімів modid для клавіатури (iris→oculus, voice→voicechat).
- `mods_loaded` у звіті порожній: знайти рядок Forge з кількістю модів у серверному і клієнтському логах.
- Деплой сервера на VPS окремим скілом; який провайдер, як оновлювати моди на сервері.
- Автооновлення збірки для друзів: повернення до Packwiz чи свій механізм. Чекає появи друзів.
- Генератор квестів як загальний скіл: формат опису квестів, відділений від даних техпаку.
- KubeJS: техпак обходиться датапаками через Paxi; чи входить KubeJS у плагін взагалі.
- MCP-сервер замість скриптів, якщо скіли впруться в ліміти.

## Out of scope

- Генерація Java-модів: окремий проєкт з Gradle і маппінгами.
- Власний лаунчер з UI: Prism уже робить авторизацію, Java і запуск.
- CurseForge API: вимагає ключ і обмежує сторонні завантаження; моди звідти додаються вручну за URL.
- Публікація збірок на Modrinth або CurseForge і будь-який обхід ліцензії гри.
