"""Hardware profile: how much memory the game may take, which tier of visuals the machine affords, which
performance mods to ship. Detection is best effort (macOS and Linux); every value can be given by hand."""
from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional

GPU_KINDS = ("apple", "nvidia", "amd", "intel", "unknown")


@dataclass
class Hardware:
    ram_gb: int
    gpu: str = "unknown"          # apple | nvidia | amd | intel | unknown
    cpu: str = ""
    os: str = ""

    @property
    def tier(self) -> str:
        """low: 8 GB or integrated Intel; mid: 16 GB, Apple Silicon or a laptop GPU; high: 32 GB and a discrete GPU."""
        if self.ram_gb < 12 or self.gpu == "intel":
            return "low"
        if self.ram_gb >= 32 and self.gpu in ("nvidia", "amd"):
            return "high"
        return "mid"

    @property
    def memory_mb(self) -> int:
        """Java heap for the client: about 40 % of RAM, between 3 and 10 GB. More than that starves the OS and
        the GPU driver, and G1 pauses grow with the heap."""
        mb = int(self.ram_gb * 1024 * 0.4)
        return max(3072, min(10240, mb // 1024 * 1024))

    @property
    def shaders(self) -> str:
        return {"low": "none", "mid": "low or medium preset", "high": "high preset"}[self.tier]

    @property
    def mod_ceiling(self) -> int:
        return {"low": 60, "mid": 130, "high": 250}[self.tier]

    def notes(self) -> list[str]:
        out = []
        if self.gpu == "apple":
            out.append("Apple Silicon: no OptiFine (not on Modrinth, breaks Forge mods); Embeddium + Oculus run shaders fine")
            out.append("keep the system input source on English when launching, macOS names keys after it")
        if self.tier == "low":
            out.append("skip the visual family (32x textures and shaders); keep worldgen light")
        if self.ram_gb >= 32:
            out.append("more heap is not faster: 8-10 GB is plenty, the rest is for the OS and the server")
        return out

    def as_dict(self) -> dict:
        d = asdict(self)
        d.update(tier=self.tier, memory_mb=self.memory_mb, shaders=self.shaders, mod_ceiling=self.mod_ceiling, notes=self.notes())
        return d


def detect() -> Hardware:
    system = platform.system()
    ram_gb, gpu, cpu = 8, "unknown", platform.processor() or ""
    try:
        if system == "Darwin":
            ram_gb = round(int(_sysctl("hw.memsize")) / 2**30)
            cpu = _sysctl("machdep.cpu.brand_string")
            gpu = "apple" if "Apple" in cpu else "intel"   # Intel Macs: integrated unless a dGPU, assume the worse
        elif system == "Linux":
            with open("/proc/meminfo") as f:
                m = re.search(r"MemTotal:\s+(\d+)", f.read())
                ram_gb = round(int(m.group(1)) / 2**20) if m else 8
            lspci = subprocess.run(["sh", "-c", "lspci 2>/dev/null | grep -i vga"], capture_output=True, text=True).stdout.lower()
            gpu = next((k for k in ("nvidia", "amd", "intel") if k in lspci), "unknown")
            with open("/proc/cpuinfo") as f:
                m = re.search(r"model name\s*:\s*(.+)", f.read())
                cpu = m.group(1).strip() if m else cpu
    except Exception:
        pass
    return Hardware(ram_gb=ram_gb, gpu=gpu, cpu=cpu, os=system.lower())


def _sysctl(name: str) -> str:
    return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=True).stdout.strip()


def from_args(ram: Optional[int], gpu: Optional[str]) -> Hardware:
    hw = detect()
    if ram:
        hw.ram_gb = ram
    if gpu:
        if gpu not in GPU_KINDS:
            raise ValueError(f"gpu must be one of {', '.join(GPU_KINDS)}")
        hw.gpu = gpu
    return hw
