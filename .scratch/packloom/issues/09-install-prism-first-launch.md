# Встановити Prism, імпортувати TechPack-1.0.0.mrpack, перший клієнтський запуск

Type: task
Status: resolved
Blocked by:

## Question

HITL-задача для Артема: поставити Prism Launcher, увійти в Microsoft-акаунт, імпортувати
/Users/artem/Projects/techpack/modpack/TechPack-1.0.0.mrpack, додати Flux Networks вручну, виставити 6 ГБ
пам'яті, запустити гру до головного меню і закрити. Результат: шлях до інстансу, реальний options.txt з
біндами модів і logs/latest.log, плюс будь-який краш. Без цього цикл перевірки і клавіатура працюють
на синтетичних даних. Чекліст уточнюється після тікета про Prism.

## Comments

- 2026-11-05 01:12: Prism встановлено, акаунт додано, mrpack імпортовано як інстанс TechPack-1.0.0 (83 jar у mods/). Був один запуск, але logs/ не створено і в options.txt нуль біндів: гра не дійшла до меню. Лишається: з'ясувати причину (лог запуску в Prism), додати Flux Networks, 6 ГБ пам'яті, дійти до меню.

## Answer

Виконано Артемом 2026-11-05 між 00:59 і 01:44: Prism встановлено (поки з ~/Downloads), акаунт додано, інстанс
TechPack-1.0.0 імпортовано, гра запущена, створено світ "New World", сесія ~10 хвилин. Результат: 143 бінди в
`minecraft/options.txt`, `logs/latest.log` (1 МБ), крашів нема. `packloom triage --client` на цьому лозі: ok, 13 помилок
(усі відомі й нешкідливі: Embeddium taint від Oculus, ModernFix reloadListener, теги DivineRPG, loot tables MEGA/ExtendedAE).
Лишається руками: перенести Prism.app в /Applications, додати Flux Networks через CurseForge у Prism.
