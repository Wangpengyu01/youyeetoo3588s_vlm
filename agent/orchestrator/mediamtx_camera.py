"""MediaMTX camera grab: WHEP (WebRTC) via GStreamer webrtcbin, or local RTSP relay."""
from __future__ import annotations

import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger(__name__)

_GRAB_LOCK = threading.Lock()
# 448×448 JPEG typically < 600KB; oversized files are corrupt or wrong pipeline (ignore).
_MAX_CACHE_BYTES = 900_000


@dataclass
class MediamtxCameraConfig:
    path: str = "cam"
    rtsp_url: str = "rtsp://127.0.0.1:8554/cam"
    whep_url: str = "http://127.0.0.1:8889/cam/whep"
    latest_frame: str = "/userdata/agent/run/mediamtx_latest.jpg"
    cache_max_age_sec: float = 0.8
    grab_backend: str = "mediamtx_rtsp"  # mediamtx_rtsp | rtsp (mediamtx_whep optional, not used for WebUI)


def uses_mediamtx(cfg: MediamtxCameraConfig) -> bool:
    b = (cfg.grab_backend or "").strip().lower()
    return b in ("mediamtx_whep", "mediamtx", "whep", "mediamtx_rtsp")


def mediamtx_cache_age_sec(cfg: MediamtxCameraConfig) -> float | None:
    latest = Path(cfg.latest_frame)
    if not _cache_file_valid(latest):
        return None
    age = time.time() - latest.stat().st_mtime
    # Board RTC drift (mtime in the future) must not count as infinitely fresh cache.
    if age < 0:
        LOG.warning("[camera] mediamtx cache mtime ahead of clock (age=%.2fs) — treat stale", age)
        return None
    return age


def mediamtx_cache_fresh(cfg: MediamtxCameraConfig) -> bool:
    age = mediamtx_cache_age_sec(cfg)
    return age is not None and age <= cfg.cache_max_age_sec


def mediamtx_cache_available(cfg: MediamtxCameraConfig) -> bool:
    """Daemon JPEG exists and decodes (any age — used to skip filler TTS before see)."""
    return _cache_file_valid(Path(cfg.latest_frame))


def _jpeg_luminance_stddev(im) -> float:
    import statistics

    from PIL import Image

    gray = im.convert("L").resize((48, 48), Image.BILINEAR)
    px = list(gray.getdata())
    if len(px) < 2:
        return 0.0
    return float(statistics.pstdev(px))


def preview_jpeg_bytes_valid(data: bytes, *, min_stddev: float = 4.0) -> bool:
    """Reject corrupt, tiny, or uniform grey placeholder JPEGs (bad WHEP/RTSP partial grabs)."""
    if len(data) < 1000 or len(data) > _MAX_CACHE_BYTES or not data.startswith(b"\xff\xd8"):
        return False
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as im:
            w, h = im.size
            if w > 512 or h > 512 or w < 64 or h < 64:
                return False
            if _jpeg_luminance_stddev(im) < min_stddev:
                LOG.warning("[camera] reject preview jpeg (blank/grey stddev<%.1f)", min_stddev)
                return False
    except Exception as exc:
        LOG.warning("[camera] reject preview jpeg (decode): %s", exc)
        return False
    return True


def _cache_file_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    size = path.stat().st_size
    if size < 1000 or size > _MAX_CACHE_BYTES:
        LOG.warning("[camera] reject mediamtx cache (size=%d): %s", size, path)
        return False
    try:
        data = path.read_bytes()
    except OSError as exc:
        LOG.warning("[camera] reject mediamtx cache (read): %s", exc)
        return False
    if not preview_jpeg_bytes_valid(data):
        LOG.warning("[camera] reject mediamtx cache (content): %s", path)
        return False
    return True


def _copy_if_fresh(src: Path, dst: Path, max_age_sec: float) -> bool:
    if not _cache_file_valid(src):
        return False
    age = time.time() - src.stat().st_mtime
    if age < 0 or age > max_age_sec:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    LOG.info("[camera] mediamtx cache hit age=%.2fs → %s", age, dst)
    return True


def grab_mediamtx_frame(cfg: MediamtxCameraConfig, save_path: Path, *, timeout: float = 12.0, size: int = 448) -> bool:
    """Grab one JPEG: daemon cache → WHEP → local mediamtx RTSP."""
    backend = (cfg.grab_backend or "mediamtx_whep").strip().lower()
    latest = Path(cfg.latest_frame)

    if _copy_if_fresh(latest, save_path, cfg.cache_max_age_sec):
        return True

    with _GRAB_LOCK:
        if _copy_if_fresh(latest, save_path, cfg.cache_max_age_sec):
            return True

        if backend in ("mediamtx_whep", "whep", "mediamtx"):
            try:
                import shutil
                import subprocess

                nice_ok = False
                if shutil.which("gst-inspect-1.0"):
                    nice_ok = (
                        subprocess.run(
                            ["gst-inspect-1.0", "nice"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        ).returncode
                        == 0
                    )
                if nice_ok:
                    from orchestrator.whep_frame import grab_whep_frame_gst

                    if grab_whep_frame_gst(cfg.whep_url, save_path, timeout=timeout, size=size):
                        return True
                else:
                    LOG.debug("[camera] skip WHEP grab (libnice missing)")
            except Exception as exc:
                LOG.warning("[camera] WHEP grab failed: %s", exc)

        if backend in ("mediamtx_whep", "mediamtx_rtsp", "mediamtx", "whep"):
            from orchestrator.rtsp_frame import grab_rtsp_frame

            if grab_rtsp_frame(
                cfg.rtsp_url,
                save_path,
                timeout=max(timeout, 8.0),
                transport="tcp",
                size=size,
            ):
                return True

    return False


def copy_mediamtx_cache_file(cfg: MediamtxCameraConfig, dest: Path) -> bool:
    """Copy latest daemon JPEG to dest (any valid age)."""
    latest = Path(cfg.latest_frame)
    if not _cache_file_valid(latest):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(latest.read_bytes())
    age = mediamtx_cache_age_sec(cfg)
    LOG.info("[camera] mediamtx cache copy (age=%s) → %s", f"{age:.2f}s" if age is not None else "?", dest)
    return True


def grab_mediamtx_vlm_pair(
    cfg: MediamtxCameraConfig,
    raw_path: Path,
    vlm_path: Path,
    *,
    timeout: float = 12.0,
    size: int = 448,
    force_live: bool = False,
    cache_only: bool = False,
) -> tuple[bool, str]:
    """
    Prepare raw + VLM JPEG for see().
    Returns (ok, source) where source is cache | mediamtx_rtsp | miss.
    """
    latest = Path(cfg.latest_frame)
    if cache_only:
        if copy_mediamtx_cache_file(cfg, vlm_path):
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(vlm_path.read_bytes())
            return True, "cache"
        return False, "miss"

    if not force_live and _copy_if_fresh(latest, vlm_path, cfg.cache_max_age_sec):
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(vlm_path.read_bytes())
        LOG.info("[camera] mediamtx VLM pair from cache (age=%.2fs)", mediamtx_cache_age_sec(cfg) or -1)
        return True, "cache"

    if grab_mediamtx_frame(cfg, vlm_path, timeout=timeout, size=size):
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(vlm_path.read_bytes())
        backend = (cfg.grab_backend or "mediamtx_rtsp").strip().lower()
        src = "mediamtx_rtsp" if backend in ("mediamtx_rtsp", "mediamtx", "rtsp") else "mediamtx_grab"
        return True, src

    return False, "miss"


def whep_reachable(whep_url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(whep_url, method="OPTIONS")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204, 405)
    except urllib.error.HTTPError as exc:
        return exc.code in (200, 204, 405)
    except Exception:
        return False
