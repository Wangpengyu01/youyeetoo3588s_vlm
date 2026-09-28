"""RTSP single-frame capture for vision / P4 (use with camera.enabled in agent.yaml)."""
from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
from pathlib import Path

LOG = logging.getLogger(__name__)

_GRAB_LOCK = threading.Lock()
_P4_GRAB = Path("/userdata/p4/scripts/rtsp_grab_once.sh")
_MAX_VLM_JPEG_BYTES = 900_000


def _is_local_mediamtx_url(url: str) -> bool:
    return "127.0.0.1" in url or ":8554/" in url


def _finalize_vlm_jpeg(path: Path, size: int) -> bool:
    """Center-crop + resize to square VLM JPEG; drop oversize/corrupt output."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size > _MAX_VLM_JPEG_BYTES:
            LOG.warning("[camera] drop oversize jpeg before normalize (%d bytes): %s", path.stat().st_size, path)
            path.unlink(missing_ok=True)
            return False
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side))
            im = im.resize((size, size), Image.BILINEAR)
            path.parent.mkdir(parents=True, exist_ok=True)
            im.save(path, format="JPEG", quality=92)
        if path.stat().st_size > _MAX_VLM_JPEG_BYTES:
            path.unlink(missing_ok=True)
            return False
        return True
    except Exception as exc:
        LOG.warning("[camera] finalize vlm jpeg failed: %s", exc)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _run_gst_live_jpeg(argv: list[str], tmp_path: Path, timeout: float) -> bool:
    """Live RTSP: stop pipeline once JPEG exists (do not wait for EOS)."""
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError:
        pass
    cmd = [a for a in argv if a != "-e"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        LOG.debug("[camera] gst spawn failed: %s", exc)
        return False
    deadline = time.monotonic() + max(float(timeout), 3.0)
    ok = False
    try:
        while time.monotonic() < deadline:
            if tmp_path.is_file() and tmp_path.stat().st_size > 1000:
                time.sleep(0.3)
                ok = True
                break
            if proc.poll() is not None:
                ok = tmp_path.is_file() and tmp_path.stat().st_size > 1000
                break
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    return ok


def grab_rtsp_via_p4_script(save_path: Path, timeout: float) -> bool:
    if not _P4_GRAB.is_file():
        return False
    out = save_path.with_suffix(".p4_grab.jpg")
    try:
        out.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        subprocess.run(
            ["bash", str(_P4_GRAB), str(out)],
            timeout=max(timeout, 12.0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if out.is_file() and out.stat().st_size > 1000:
            out.replace(save_path)
            return save_path.is_file()
    except Exception as exc:
        LOG.debug("[camera] p4 grab failed: %s", exc)
    return False


def grab_rtsp_frame(
    url: str,
    save_path: Path,
    *,
    timeout: float = 15.0,
    transport: str = "tcp",
    size: int = 448,
) -> bool:
    tmp_path = save_path.with_suffix(".rtsp_tmp.jpg")
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError:
        pass

    devnull = subprocess.DEVNULL
    local_mediamtx = _is_local_mediamtx_url(url)
    gst_timeout = max(float(timeout), 15.0 if local_mediamtx else float(timeout))
    proto = "tcp" if transport == "tcp" else transport

    def _try_gst(cmd: list[str]) -> bool:
        if _run_gst_live_jpeg(cmd, tmp_path, gst_timeout):
            tmp_path.replace(save_path)
            return _finalize_vlm_jpeg(save_path, size)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False

    with _GRAB_LOCK:
        if not local_mediamtx and grab_rtsp_via_p4_script(save_path, timeout=timeout):
            return _finalize_vlm_jpeg(save_path, size)

        gst_mpp = [
            "gst-launch-1.0", "-e",
            "rtspsrc", f"location={url}", f"protocols={proto}", "latency=200", "drop-on-latency=true", "!",
            "rtph264depay", "!", "h264parse", "!", "mppvideodec", "!",
            "videoconvert", "!", "videoscale", "!",
            f"video/x-raw,width={size},height={size}", "!",
            "jpegenc", "quality=90", "!",
            "filesink", f"location={tmp_path}", "sync=false", "async=false",
        ]
        if _try_gst(gst_mpp):
            return True

        gst_gen = [
            "gst-launch-1.0", "-e",
            "rtspsrc", f"location={url}", f"protocols={proto}", "latency=200", "drop-on-latency=true", "!",
            "decodebin", "!", "videoconvert", "!", "videoscale", "!",
            f"video/x-raw,width={size},height={size}", "!",
            "jpegenc", "quality=90", "!",
            "filesink", f"location={tmp_path}", "sync=false", "async=false",
        ]
        if _try_gst(gst_gen):
            return True

        # Never P4-direct for localhost relay — it bypasses mediamtx and yields 640×480 / multi-MB JPEGs.
        if not local_mediamtx and grab_rtsp_via_p4_script(save_path, timeout=timeout):
            return _finalize_vlm_jpeg(save_path, size)

    return False
