# Demo

**Explainer video (2:36)**: one illustrated scene per step with narration and subtitles, on the hosted demo page
https://claude.ai/artifact/UMSf4z353D2BnkRF41htxD (private until shared) and as `packloom-explainer.mp4` in the release assets.

**Terminal recording.** A recorded terminal session, about half a minute with idle time compressed, on TechPack 1.2.0 (1.20.1 Forge, 85 files):

1. `catalog tags` and `design`: a wish list of tags becomes 15 families and 73 mods.txt lines, with reasons.
2. `hardware`: the machine (M1 Pro, 16 GB) sets the heap and the visual tier.
3. `tune check`: the hard preset touches two recipes; a typo in an item id is caught with a "did you mean".
4. `build --server` and `test --skip-build`: the mrpack is written and a headless Forge server comes up with
   KubeJS, then `tune verify` compares what tune.json expects with what the server did.
5. `keys --json`: the keyboard map summary.

**Watch it**: [demo.html](demo.html) (open locally, it plays `demo.cast` with asciinema-player from a CDN),
or the hosted copy: https://claude.ai/artifact/UMSf4z353D2BnkRF41htxD (private until shared). Play it back in a terminal with
[asciinema](https://asciinema.org): `asciinema play docs/demo.cast`.

The recording is produced by a 60-line script that runs each command in a pseudo-terminal and writes
[asciicast v2](https://docs.asciinema.org/manual/asciicast/v2/); nothing in it is typed by hand, so it can be
re-recorded after every release.
