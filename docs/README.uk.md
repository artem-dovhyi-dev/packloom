# packloom: коротко українською

**Описуєш збірку словами, отримуєш збірку, яка запускається.**

packloom це плагін для Claude Code і звичайна утиліта на Python (без залежностей), яка робить із модпаку
текст: `mods.txt` з модами, `tune.json` з рецептами і складністю, `pack.json` з налаштуваннями. Усе інше
(версії з Modrinth, залежності, mrpack, тестовий сервер, скрипти KubeJS) робить команда або агент.

## Що вміє

| Кажеш | Команда | Результат |
|---|---|---|
| «хочу RPG і індустрію, трохи ферм, гарний світ, без грайнду, з друзями» | `/pack-design` | спершу інтерактивна сторінка каталогу (артефакт): теги, рівень гринду, картки родин, кнопка **Hand to Claude** передає вибір назад; `design --picks picks.json` збирає `mods.txt` саме з цього вибору. Каталог: 80 родин (Thermal, Create, Mekanism, AE2, Immersive Engineering, Aether, Botania, Macaw's, Fresh Animations…), кожен мод перевірено на Modrinth; QoL (JEI, сортування інвентарю, пошук клавіш), оптимізація, баланс (Almost Unified, Polymorph) і текстури Faithful йдуть за замовчуванням і вже ввімкнені |
| «зроби важче» / «меч, що поєднує DivineRPG і Thermal» / «хай лінії перетинаються» | `tune` | `tune.json` → скрипти KubeJS; кожен id звірено з реєстром предметів; **інтеграції** між модами як окремі блоки (у TechPack їх 19: пил Divine-руд у Thermal і Mekanism, сплав Fluxed Realmite, броня Osmic Arlemite, Інсолятор ростить Farmer's Delight…), `tune doc` пише `INTEGRATIONS.md` для гравців |
| «має тягнути на моєму M1 з 16 ГБ» | `hardware` | heap, рівень шейдерів, моди оптимізації |
| «яка клавіша що робить?» | `keys` | сторінка `keybinds.html` з клавіатурою |
| «воно взагалі запускається?» | `build`, `test`, `triage` | mrpack, тестовий сервер без вікна, підозрювані моди з логу |

## Швидкий старт

```bash
alias packloom='PYTHONPATH=/шлях/до/packloom/lib python3 -m packloom'
mkdir mypack && cd mypack
packloom init --name MyPack --minecraft 1.20.1 --loader forge
packloom design --want tech,rpg,farming,worldgen,coop --no-grind --include divinerpg --detect --verify --write
packloom hardware --apply
packloom build --server && packloom test --accept-eula
packloom tune init && packloom registry && packloom tune build && packloom tune doc
packloom bundle
```

Далі Prism Launcher → Add Instance → Import → файл `.mrpack`.

## Як підключити до Claude Code

У `.claude/settings.json` проєкту зі збіркою:

```json
{ "extraKnownMarketplaces": { "packloom": { "source": { "source": "github", "repo": "artem-dovhyi-dev/packloom", "ref": "main" } } },
  "enabledPlugins": { "packloom@packloom": true } }
```

З'являться команди `/pack-design`, `/pack-build`, `/pack-test`, `/pack-triage`, `/pack-tune`, `/pack-icons`, `/pack-hardware`, `/pack-keys`.

## Чого не робить

Не качає з CurseForge (такі моди позначаються `manual:` і ставляться рукою), не запускає гру (це робить
Prism), не малює текстури (генерує заглушки, `INTEGRATIONS.md` каже, що намалювати), не вирішує, що весело.
Каталог це одна думка: одна родина на задачу, аддони перелічені, але не нав'язані, без грайнду.

Повна документація англійською: [README.md](../README.md), [use-cases.md](use-cases.md), [tutorial.md](tutorial.md),
[tune.md](tune.md), [integrations.md](integrations.md), [catalog.md](catalog.md), [демо](demo.md).
