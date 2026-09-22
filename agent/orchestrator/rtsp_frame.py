"""RTSP single-frame capture for vision / P4 (use with camera.enabled in agent.yaml)."""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

LOG = logging.getLogger(__name__)

_GRAB_LOCK = threading.Lock()
_P4_GRAB = Path("/userdata/p4/scripts/rtsp_grab_once.sh")


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
            return True
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
    with _GRAB_LOCK:
        if grab_rtsp_via_p4_script(save_path, timeout=timeout):
            return True

        gst_mpp = [
            "gst-launch-1.0", "-e",
            "rtspsrc", f"location={url}", f"protocols={transport}", "latency=200", "drop-on-latency=true", "!",
            "rtph264depay", "!", "h264parse", "!", "mppvideodec", "!",
            "videoconvert", "!", "videoscale", "!",
            f"video/x-raw,width={size},height={size}", "!",
            "jpegenc", "quality=90", "!",
            "filesink", f"location={tmp_path}", "sync=false", "async=false",
        ]
        try:
            subprocess.run(gst_mpp, stdout=devnull, stderr=devnull, timeout=timeout, check=False)
            if tmp_path.is_file() and tmp_path.stat().st_size > 1000:
                tmp_path.replace(save_path)
                return True
        except Exception:
            pass

        gst_gen = [
            "gst-launch-1.0", "-e",
            "rtspsrc", f"location={url}", f"protocols={transport}", "latency=200", "drop-on-latency=true", "!",
            "decodebin", "!", "videoconvert", "!", "videoscale", "!",
            f"video/x-raw,width={size},height={size}", "!",
            "jpegenc", "quality=90", "!",
            "filesink", f"location={tmp_path}", "sync=false", "async=false",
        ]
        try:
            subprocess.run(gst_gen, stdout=devnull, stderr=devnull, timeout=timeout, check=False)
            if tmp_path.is_file() and tmp_path.stat().st_size > 1000:
                tmp_path.replace(save_path)
                return True
        except Exception:
            pass

        if grab_rtsp_via_p4_script(save_path, timeout=timeout):
            return True

    return False
