#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone Camera VLM and TTS Integration Test Script (Xiao Lan)

Captures frames from a network camera (default: http://10.0.0.159:8080/shot.jpg),
prepares the frame for VLM inference (InternVL3.5 / API / Mock),
and speaks the visual description via TTS (Matcha-TTS on board or SAPI on PC).
"""

import argparse
import base64
import io
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from PIL import Image

DEFAULT_CAMERA_URL = "http://10.0.0.159:8080/shot.jpg"
DEFAULT_PROMPT = "用简短的一句话描述当前画面中的主要物体和场景。"


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def get_temp_dir() -> Path:
    if is_linux():
        return Path("/tmp")
    return Path(os.getenv("TEMP", "C:/tmp"))


def grab_camera_frame(url: str, save_path: Path, timeout: float = 3.0) -> bool:
    """Fetch snapshot JPEG from network camera HTTP endpoint or local test file."""
    if os.path.exists(url):
        import shutil
        save_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(url, save_path)
        print(f"[Camera] 使用本地测试画面: {url} -> {save_path}", flush=True)
        return True

    normalized_url = url.rstrip("/")
    if not normalized_url.startswith("file://"):
        if not normalized_url.endswith(".jpg") and not normalized_url.endswith(".jpeg"):
            normalized_url += "/shot.jpg"

    print(f"[Camera] 正在拉取画面: {normalized_url} ...", flush=True)
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(
            normalized_url,
            headers={"User-Agent": "XiaoLan-CameraClient/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(data)

        ms = (time.monotonic() - t0) * 1000
        print(f"[Camera] 抓帧成功: {len(data)} bytes ({ms:.1f}ms) -> {save_path}", flush=True)
        return True
    except Exception as exc:
        print(f"[Camera] 抓帧失败: {exc}", file=sys.stderr)
        return False


def prepare_vlm_frame(src_path: Path, dst_path: Path, size: int = 448) -> Image.Image:
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    cropped = im.crop((left, top, left + side, top + side))
    resized = cropped.resize((size, size), Image.BILINEAR)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    resized.save(dst_path, format="JPEG", quality=92)
    print(f"[Preprocess] 缩放裁切: {w}x{h} -> {size}x{size} -> {dst_path}", flush=True)
    return resized


def compute_frame_motion(img_a: Image.Image, img_b: Image.Image) -> float:
    thumb_a = img_a.resize((64, 64)).convert("L")
    thumb_b = img_b.resize((64, 64)).convert("L")
    bytes_a = thumb_a.tobytes()
    bytes_b = thumb_b.tobytes()
    diff = sum(abs(a - b) for a, b in zip(bytes_a, bytes_b)) / len(bytes_a)
    return float(diff)


def run_board_rknn_vlm(frame_path: Path, prompt: str) -> str:
    vlm_see_sh = Path("/userdata/p4/scripts/vlm_see.sh")
    if not vlm_see_sh.exists():
        vlm_see_sh = Path(__file__).resolve().parent / "vlm_see.sh"

    if vlm_see_sh.exists():
        cmd = ["bash", str(vlm_see_sh), str(frame_path), prompt]
        print(f"[VLM] 启动板载 NPU 推理: {cmd}", flush=True)
        t0 = time.monotonic()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ms = (time.monotonic() - t0) * 1000
        lines = [ln.strip() for ln in res.stdout.strip().splitlines() if ln.strip()]
        caption = lines[-1] if lines else ""
        print(f"[VLM] 推理完成 ({ms:.1f}ms): {caption}", flush=True)
        return caption
    
    print("[VLM] 未找到板载 vlm_see.sh，回退到规则分析", flush=True)
    return ""


def run_cloud_vlm_api(frame_path: Path, prompt: str, api_url: str, api_key: str, model: str) -> str:
    with open(frame_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("ascii")
    
    endpoint = api_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                ]
            }
        ],
        "max_tokens": 128,
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    ms = (time.monotonic() - t0) * 1000
    caption = result["choices"][0]["message"]["content"].strip()
    print(f"[VLM-API] 云端推理完成 ({ms:.1f}ms): {caption}", flush=True)
    return caption


def run_mock_vlm(src_path: Path, prompt: str) -> str:
    im = Image.open(src_path)
    w, h = im.size
    gray = im.convert("L")
    raw_bytes = gray.tobytes()
    avg_luma = sum(raw_bytes) / len(raw_bytes)
    
    if avg_luma < 30:
        luma_desc = "画面偏暗"
    elif avg_luma > 200:
        luma_desc = "画面光线较强"
    else:
        luma_desc = "光线良好清晰"
        
    return f"网络摄像头连接正常，画面分辨率为{w}乘{h}，{luma_desc}。"


def speak_text(text: str) -> None:
    clean_text = text.strip().replace("\n", "，")
    if not clean_text:
        return

    print(f"[TTS] 播报文本: {clean_text}", flush=True)

    if is_linux():
        tts_sh = Path("/userdata/voice/scripts/tts.sh")
        if tts_sh.exists():
            subprocess.run(["bash", str(tts_sh), clean_text], check=False)
            return
        
        sherpa_tts = Path("/userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu/bin/sherpa-onnx-offline-tts")
        if sherpa_tts.exists():
            out_wav = "/tmp/vlm_caption.wav"
            cmd = [
                str(sherpa_tts),
                "--matcha-acoustic-model=/userdata/voice/matcha-icefall-zh-baker/model-steps-3.onnx",
                "--matcha-vocoder=/userdata/voice/vocos-22khz-univ.onnx",
                "--matcha-lexicon=/userdata/voice/matcha-icefall-zh-baker/lexicon.txt",
                "--matcha-tokens=/userdata/voice/matcha-icefall-zh-baker/tokens.txt",
                "--matcha-dict-dir=/userdata/voice/matcha-icefall-zh-baker/dict",
                f"--output-filename={out_wav}",
                clean_text,
            ]
            subprocess.run(cmd, check=False)
            play_sh = Path("/userdata/voice/scripts/play_wav.sh")
            if play_sh.exists():
                subprocess.run(["bash", str(play_sh), out_wav], check=False)
            else:
                subprocess.run(["aplay", "-D", "plughw:0,0", out_wav], check=False)
            return
        print("[TTS] 板端未找到 tts.sh 或 sherpa-tts", flush=True)
    else:
        try:
            ps_cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Speak('{clean_text}')"
            )
            subprocess.run(["powershell", "-Command", ps_cmd], check=False)
        except Exception as e:
            print(f"[TTS] Windows 语音播放跳过: {e}", flush=True)


def run_single_turn(args) -> None:
    temp_dir = get_temp_dir()
    raw_frame_path = temp_dir / "camera_raw.jpg"
    vlm_frame_path = temp_dir / "vlm_frame.jpg"

    ok = grab_camera_frame(args.url, raw_frame_path, timeout=args.timeout)
    if not ok:
        print("[Error] 无法从网络摄像头获取画面，请检查 IP/端口是否正常。", file=sys.stderr)
        return

    prepare_vlm_frame(raw_frame_path, vlm_frame_path, size=args.size)

    caption = ""
    if args.api_url and args.api_key:
        try:
            caption = run_cloud_vlm_api(
                vlm_frame_path, args.prompt, args.api_url, args.api_key, args.model
            )
        except Exception as exc:
            print(f"[VLM-API] 接口调用异常: {exc}", file=sys.stderr)

    if not caption and (args.mode in ("auto", "rknn") and is_linux()):
        caption = run_board_rknn_vlm(vlm_frame_path, args.prompt)

    if not caption:
        caption = run_mock_vlm(raw_frame_path, args.prompt)

    print("\n" + "=" * 50)
    print(f"【小榄视觉描述】: {caption}")
    print("=" * 50 + "\n")

    if args.tts:
        speak_text(caption)


def run_loop_monitoring(args) -> None:
    print("[Loop] 启动贾维斯式主动场景感知循环 (Ctrl+C 退出)...", flush=True)
    temp_dir = get_temp_dir()
    raw_frame_path = temp_dir / "camera_raw.jpg"
    vlm_frame_path = temp_dir / "vlm_frame.jpg"
    
    last_img = None
    last_speak_time = 0.0

    while True:
        try:
            ok = grab_camera_frame(args.url, raw_frame_path, timeout=args.timeout)
            if ok:
                cur_img = Image.open(raw_frame_path).convert("RGB")
                if last_img is not None:
                    motion = compute_frame_motion(last_img, cur_img)
                    print(f"[Motion] 画面动态指数: {motion:.2f} (阈值: {args.motion_threshold})", flush=True)
                    
                    now = time.monotonic()
                    if motion >= args.motion_threshold and (now - last_speak_time >= args.cooldown):
                        print("[Motion] >>> 检测到显著画面变化，触发小榄主动视觉解读！<<<", flush=True)
                        prepare_vlm_frame(raw_frame_path, vlm_frame_path, size=args.size)
                        
                        caption = ""
                        if args.api_url and args.api_key:
                            caption = run_cloud_vlm_api(vlm_frame_path, args.prompt, args.api_url, args.api_key, args.model)
                        elif is_linux():
                            caption = run_board_rknn_vlm(vlm_frame_path, args.prompt)
                        
                        if not caption:
                            caption = "检测到画面中有动态变化，小榄已关注到您的动作。"
                            
                        print(f"【主动提醒】: {caption}")
                        if args.tts:
                            speak_text(caption)
                        last_speak_time = time.monotonic()
                    else:
                        print("[Status] 画面平稳或冷却中，保持安静...", flush=True)
                
                last_img = cur_img

            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[Loop] 退出循环监测。")
            break
        except Exception as exc:
            print(f"[Loop] 异常: {exc}", file=sys.stderr)
            time.sleep(args.interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Xiao Lan Network Camera VLM and TTS Test")
    parser.add_argument("--url", default=DEFAULT_CAMERA_URL, help="Network camera URL")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="VLM text prompt")
    parser.add_argument("--mode", choices=["auto", "rknn", "api", "mock"], default="auto", help="Inference mode")
    parser.add_argument("--size", type=int, default=448, help="VLM input square size")
    parser.add_argument("--timeout", type=float, default=3.0, help="Camera HTTP timeout in seconds")
    parser.add_argument("--api-url", default=os.getenv("VLM_API_URL", ""), help="OpenAI-compatible VLM endpoint")
    parser.add_argument("--api-key", default=os.getenv("VLM_API_KEY", ""), help="API Key for cloud VLM")
    parser.add_argument("--model", default="qwen-vl-max", help="Model name for API mode")
    parser.add_argument("--no-tts", dest="tts", action="store_false", help="Disable TTS speech output")
    parser.add_argument("--loop", action="store_true", help="Continuous proactive monitoring loop")
    parser.add_argument("--interval", type=float, default=2.5, help="Loop interval seconds")
    parser.add_argument("--motion-threshold", type=float, default=12.0, help="Motion detection threshold")
    parser.add_argument("--cooldown", type=float, default=10.0, help="Cooldown between alerts")
    
    args = parser.parse_args()

    if args.loop:
        run_loop_monitoring(args)
    else:
        run_single_turn(args)


if __name__ == "__main__":
    main()
