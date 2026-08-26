#!/usr/bin/env python3
"""Probe all ES8388 mic routes; pick the loudest while you speak."""
import math
import os
import struct
import subprocess
import wave

ROUTES = [
    "headset_line2",   # 3.5mm TRRS 耳机麦常用
    "headset_miclr",
    "headset_line1",
    "main_board",
]

CARD = 0
SEC = int(os.environ.get("MIC_PROBE_SEC", "3"))


def read_mixer(numid: int) -> str:
    p = subprocess.run(
        ["amixer", "-c", str(CARD), "cget", f"numid={numid}"],
        capture_output=True,
        text=True,
    )
    for line in p.stdout.splitlines():
        if line.startswith("  : values="):
            return line.split("=", 1)[1].strip()
    return "?"


def apply_route(name: str) -> None:
    env = os.environ.copy()
    env["MIC_ROUTE"] = name
    env["MIC_SOURCE"] = "headset" if name.startswith("headset") else "main"
    subprocess.run(
        ["bash", "/userdata/voice/scripts/mic_arm.sh"],
        env=env,
        check=False,
    )


def record(path: str, stereo: bool = True) -> None:
    ch = 2 if stereo else 1
    subprocess.run(
        [
            "arecord",
            "-q",
            "-D",
            "plughw:0,0",
            "-f",
            "S16_LE",
            "-r",
            "16000",
            "-c",
            str(ch),
            "-d",
            str(SEC),
            path,
        ],
        check=True,
    )


def analyze(path: str):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    if ch == 2:
        left = samples[0::2]
        right = samples[1::2]
        peak_l = max((abs(x) for x in left), default=0)
        peak_r = max((abs(x) for x in right), default=0)
        use = left if peak_l >= peak_r else right
        peak = max(peak_l, peak_r)
        side = "L" if peak_l >= peak_r else "R"
    else:
        use = samples
        peak = max((abs(x) for x in use), default=0)
        side = "M"
    rms = math.sqrt(sum(x * x for x in use) / len(use)) if use else 0.0
    hot = sum(1 for x in use if abs(x) > 500)
    pct = 100.0 * hot / len(use) if use else 0.0
    return peak, rms, pct, side


def main() -> None:
    hp = read_mixer(26)
    hsm = read_mixer(27)
    print("=== R1 咪头路由探测 ===")
    print(f"Headphone Jack={hp}  Headset Mic Jack={hsm}")
    print(f"请对着 3.5mm 耳机麦或板载麦说话，每路录 {SEC}s …")
    print()

    best_name, best_score, best_peak = None, -1.0, 0
    rows = []

    for name in ROUTES:
        apply_route(name)
        wav = f"/tmp/mic_probe_{name}.wav"
        record(wav, stereo=True)
        peak, rms, pct, side = analyze(wav)
        score = rms * (1.0 + pct / 100.0)
        rows.append((name, peak, rms, pct, side, score))
        if score > best_score:
            best_score, best_name, best_peak = score, name, peak

    print(f"{'route':16s} {'peak':>7s} {'rms':>8s} {'active':>7s} ch")
    for name, peak, rms, pct, side, _ in rows:
        mark = " <-- best" if name == best_name else ""
        print(f"  {name:14s} {peak:7d} {rms:8.1f} {pct:6.1f}% {side}{mark}")

    print()
    if best_peak < 800:
        print("警告: 所有路由 peak 都很低。")
        if hsm == "off":
            print("  Headset Mic Jack=off → 3.5mm 可能不是 TRRS 耳机麦（TRS 音响无麦）。")
        print("  请确认插头是 4 段 TRRS，或换板载麦时拔掉 3.5mm 再测 main_board。")
    print(f"推荐: export MIC_ROUTE={best_name}")
    if best_name.startswith("headset"):
        print("       export MIC_SOURCE=headset")


if __name__ == "__main__":
    main()
