# Контракт циклу перевірки: що smoke-тест повертає агенту і що triage може робити сам

Type: grilling
Status: resolved
Blocked by: 03, 04

## Question

Який структурований результат повертає modpack-test (успіх, час до Done, список помилок і варнінгів по модах),
як modpack-triage мапить стектрейс або mixin-помилку на конкретний мод, які дії агент робить сам (прибрати мод,
змінити конфіг, відкотити версію) і які лише пропонує, і як клієнтський лог Prism потрапляє в той самий цикл.
Результат: формат звіту тесту (JSON) і правила автономності triage.

## Answer

`pack-test` пише `smoke-report.json` поруч із збіркою:
```json
{ "ok": true, "seconds": 102, "mods_loaded": "Loaded 83 mods", "errors": ["..."], "warnings": 14,
  "missing_deps": ["..."], "crash_report": "server/crash-reports/crash-....txt", "suspects": [
    { "mod": "lithostitched", "evidence": "Mixin apply failed lithostitched.mixins.json ...", "kind": "mixin" } ] }
```
`suspects` будуються евристиками: modid із mixin-помилок (`Mixin apply for mod X failed`), перший не-`minecraft`/
не-`forge` пакет у стектрейсі краш-репорту, modid з `Missing or unsupported mandatory dependencies`, і секція
`Mod List` краш-репорту для зіставлення пакета з jar. Якщо підозрюваних немає, звіт це каже, а не вигадує.

Автономність triage: сам може лише перезапустити тест і запропонувати дію у звіті (`remove`, `pin`,
`add-dependency`, `config`). Зміни в mods.txt робить окремий крок `pack-build --apply <proposal>` або людина.
У нічному режимі, коли Артем явно дозволив діяти самостійно, агент застосовує пропозицію і пише, що зробив.

Клієнтський бік: `pack-triage --client` шукає інстанс Prism за `ManagedPackName` у `instance.cfg`, читає
`minecraft/logs/latest.log` і останній `crash-reports/*.txt`, і прогоняє ті самі евристики. Форма звіту та сама.
Серверна установка Forge теж у `pack-test`: якщо `server/run.sh` відсутній, тягне інсталер з files.minecraftforge.net
і запускає `--installServer`, приймає EULA лише з прапором `--accept-eula`, бо це юридична дія людини.
