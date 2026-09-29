#!/usr/bin/env python3
"""High-performance streaming Web UI server for XiaoLan (stdlib only).
Serves static UI files and streams live MJPEG video (/video_feed) from phone camera.
"""
from __future__ import annotations

import http.server
import logging
import os
from pathlib import Path
import socketserver
import threading
import time
import urllib.request

LOG = logging.getLogger("ui_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

UI_DIR = Path(__file__).parent.resolve()
AGENT_ROOT = UI_DIR.parent
DEFAULT_CAMERA_URL = "http://10.42.0.23:8080/video"


def discover_camera_url() -> str:
    """Find active camera URL on hotspot or fallback to config."""
    try:
        # Check active DHCP leases first
        lease_file = Path("/var/lib/NetworkManager/dnsmasq-wlP4p65s0.leases")
        if lease_file.is_file():
            try:
                for line in lease_file.read_text(encoding="utf-8").splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and parts[2].startswith("10.42.0."):
                        return f"http://{parts[2]}:8080/video"
            except Exception:
                pass

        # Check reachable ARP entries
        if os.path.isfile("/proc/net/arp"):
            with open("/proc/net/arp", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 6 and "wl" in parts[5]:
                        ip, flags, hw = parts[0], parts[2], parts[3]
                        if ip.startswith("10.42.0.") and flags == "0x2" and hw != "00:00:00:00:00:00":
                            return f"http://{ip}:8080/video"
    except Exception:
        pass
    return DEFAULT_CAMERA_URL


class StreamBuffer:
    def __init__(self) -> None:
        self.frame: bytes | None = None
        self.lock = threading.Lock()
        self.last_update: float = 0.0

    def update(self, frame: bytes) -> None:
        with self.lock:
            self.frame = frame
            self.last_update = time.monotonic()

    def get(self) -> tuple[bytes | None, float]:
        with self.lock:
            return self.frame, self.last_update


buffer = StreamBuffer()


def camera_stream_worker() -> None:
    """Continuously pulls MJPEG stream from camera and keeps latest frame in buffer."""
    LOG.info("Starting background camera stream worker...")
    while True:
        try:
            url = discover_camera_url()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "XiaoLan-UIProxy/1.0"},
            )
            LOG.info("Connecting to camera live stream: %s", url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                stream_bytes = bytearray()
                frame_count = 0
                last_fps_time = time.monotonic()
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    stream_bytes.extend(chunk)
                    a = stream_bytes.find(b"\xff\xd8")
                    b = stream_bytes.find(b"\xff\xd9", a + 2) if a != -1 else -1
                    if a != -1 and b != -1:
                        jpg = bytes(stream_bytes[a : b + 2])
                        buffer.update(jpg)
                        frame_count += 1
                        now = time.monotonic()
                        if now - last_fps_time >= 5.0:
                            fps = frame_count / (now - last_fps_time)
                            LOG.info("Camera stream running at %.1f FPS (size=%d bytes)", fps, len(jpg))
                            frame_count = 0
                            last_fps_time = now
                            # Periodically update latest_frame.jpg file on disk
                            try:
                                (UI_DIR / "latest_frame.jpg").write_bytes(jpg)
                            except Exception:
                                pass
                        stream_bytes = stream_bytes[b + 2 :]
        except Exception as exc:
            LOG.warning("Camera stream disconnected (%s), retrying in 1.5s...", exc)
            time.sleep(1.5)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class StreamingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/video_feed", "/stream.mjpg", "/live", "/video"):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()

            last_sent_time = 0.0
            try:
                while True:
                    frame, update_time = buffer.get()
                    if frame and update_time != last_sent_time:
                        last_sent_time = update_time
                        self.wfile.write(b"--frame\r\n")
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(frame)))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.02)  # Max 50 FPS
            except (ConnectionResetError, BrokenPipeError):
                pass
        else:
            super().do_GET()

    def log_message(self, fmt: str, *args: Any) -> None:
        # Suppress logging for repeated static and stream requests to avoid clutter
        if "/video_feed" not in str(args) and "/latest_frame" not in str(args):
            super().log_message(fmt, *args)


def main() -> None:
    port = int(os.environ.get("UI_PORT", 8766))
    host = os.environ.get("UI_HOST", "0.0.0.0")

    # Start live camera streaming thread
    worker_th = threading.Thread(target=camera_stream_worker, daemon=True, name="CameraStreamWorker")
    worker_th.start()

    server = ThreadedHTTPServer((host, port), StreamingHandler)
    LOG.info("XiaoLan Live Video Stream UI Server listening on http://%s:%d", host, port)
    LOG.info("Direct Live 30FPS stream available at: http://%s:%d/video_feed", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
