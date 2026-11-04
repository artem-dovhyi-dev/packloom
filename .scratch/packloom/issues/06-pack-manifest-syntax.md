# Синтаксис mods.txt і pack.json: джерела поза Modrinth, клієнт/сервер, версії

Type: grilling
Status: resolved
Blocked by:

## Question

Як описувати в mods.txt моди, яких немає на Modrinth (прямий URL, FTB maven, ручний CurseForge як у Flux Networks),
як фіксувати конкретну версію мода замість останньої сумісної, як позначати client-only та server-only,
і яка схема pack.json. Обмеження: формат має лишатися зрозумілим для людини і простим для діфу в git.
Результат: специфікація обох файлів з прикладами, включно з 11 модами техпаку, яких не знайшлось на Modrinth
(список у build-report.md і сесії техпаку).

## Answer

pack.json:
```json
{ "name": "TechPack", "version": "1.0.0", "minecraft": "1.20.1", "loader": "forge",
  "loader_version": "recommended", "memory_mb": 6144 }
```
`loader_version` = `recommended`, `latest` або точний номер. `memory_mb` для серверного тесту і підказки клієнту.

mods.txt, один запис на рядок, `#` коментар, порожні рядки і заголовки `# --- ... ---` ігноруються:
- `slug` — проєкт Modrinth, остання стабільна версія під гру і лоадер (як зараз).
- `slug@1.4.18` — закріплена `version_number` з Modrinth; збірка падає з помилкою, якщо такої версії нема.
- `slug client` або `slug server` — перевизначення сторони; без слова сторона береться з Modrinth за старим
  правилом (клієнт завжди required, сервер unsupported лише коли Modrinth так каже).
- `ftb:ftb-quests-forge` — артефакт з maven FTB, остання не-SNAPSHOT версія гілки гри; jar кладеться в
  `overrides/mods`, бо mrpack-формат дозволяє завантаження лише з Modrinth, GitHub і GitLab.
- `url:https://.../mod.jar` — прямий jar, теж в `overrides/mods`; необов'язковий `sha256=...` після пробілу.
- `manual:flux-networks  # CurseForge` — не завантажується, потрапляє в build-report і README як ручний крок.
Порядок і коментарі зберігаються, бо файл правиться руками і діфиться в git. Старий techpack/mods.txt
валідний без змін: чотири FTB-моди і Flux Networks просто переписуються з коментарів у `ftb:` і `manual:`.
