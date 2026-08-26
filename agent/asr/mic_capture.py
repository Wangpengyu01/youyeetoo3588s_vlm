"""Microphone capture helpers — reuse frozen R1 voice hardware scripts."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

VOICE_SCRIPTS = Path(os.environ.get("VOICE_SCRIPTS", "/userdata/voice/scripts"))


def arm_mic() -> None:
    script = VOICE_SCRIPTS / "mic_arm.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    subprocess.run(["bash", str(script)], check=True)


def setup_mic() -> None:
    script = VOICE_SCRIPTS / "mic_setup.sh"
    if script.is_file():
        subprocess.run(["bash", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def mic_route_guard(stop: asyncio.Event, interval: float = 0.08) -> None:
    """Keep ES8388 mic route locked while recording (same idea as mic_record.sh)."""
    while not stop.is_set():
        setup_mic()
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def open_arecord(
    *,
    device: str = "plughw:0,0",
    sample_rate: int = 16000,
    channels: int = 1,
) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        "arecord",
        "-q",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-r",
        str(sample_rate),
        "-c",
        str(channels),
        "-t",
        "raw",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
