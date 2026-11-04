"""Find or fetch a JDK of the right major version without sudo.
Order: packloom cache -> /usr/libexec/java_home -> Prism Launcher's runtime -> Adoptium API download."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from typing import Optional

from .http import download, get_text, request

CACHE = Path(os.environ.get("PACKLOOM_CACHE", Path.home() / ".cache" / "packloom"))
PRISM_RUNTIMES = {17: "java-runtime-gamma", 21: "java-runtime-delta", 16: "java-runtime-alpha", 8: "jre-legacy"}


def java_version(java: Path) -> Optional[int]:
    try:
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out.stderr + out.stdout)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2)) if major == 1 and m.group(2) else major


def _candidates(major: int):
    yield from sorted(CACHE.glob(f"jdk{major}/*/Contents/Home/bin/java"))
    yield from sorted(CACHE.glob(f"jdk{major}/*/bin/java"))
    if shutil.which("/usr/libexec/java_home"):
        try:
            home = subprocess.run(["/usr/libexec/java_home", "-v", str(major)], capture_output=True,
                                  text=True, timeout=20).stdout.strip()
            if home:
                yield Path(home) / "bin" / "java"
        except (OSError, subprocess.TimeoutExpired):
            pass
    prism = Path.home() / "Library" / "Application Support" / "PrismLauncher" / "java"
    if major in PRISM_RUNTIMES:
        yield prism / PRISM_RUNTIMES[major] / "bin" / "java"
    env = os.environ.get("JAVA_HOME")
    if env:
        yield Path(env) / "bin" / "java"


def find_java(major: int, allow_download: bool = True, log=print) -> Path:
    for java in _candidates(major):
        if java.is_file() and java_version(java) == major:
            return java
    if not allow_download:
        raise RuntimeError(f"no Java {major} found; run with --download-java or install Temurin {major}")
    return download_jdk(major, log)


def download_jdk(major: int, log=print) -> Path:
    os_name = {"Darwin": "mac", "Linux": "linux", "Windows": "windows"}[platform.system()]
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x64", "AMD64": "x64"}[platform.machine()]
    api = f"https://api.adoptium.net/v3/binary/latest/{major}/ga/{os_name}/{arch}/jdk/hotspot/normal/eclipse"
    with urllib.request.urlopen(request(api), timeout=60) as r:
        final_url = r.geturl()
    sha = get_text(final_url + ".sha256.txt").split()[0]
    archive = CACHE / f"jdk{major}" / final_url.rsplit("/", 1)[-1]
    log(f"downloading Temurin {major} from {final_url}")
    download(final_url, archive, sha256=sha)
    target = archive.parent
    with tarfile.open(archive) as tar:
        tar.extractall(target)
    archive.unlink()
    java = next(iter(_candidates(major)), None)
    if not java or java_version(java) != major:
        raise RuntimeError(f"unpacked JDK under {target} but no usable bin/java")
    return java
