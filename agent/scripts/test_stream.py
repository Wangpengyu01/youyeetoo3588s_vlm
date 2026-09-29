import urllib.request
import time

t0 = time.time()
req = urllib.request.Request("http://10.42.0.23:8080/video", headers={"User-Agent": "XiaoLan-StreamTest/1.0"})
with urllib.request.urlopen(req, timeout=3) as resp:
    buf = bytearray()
    while len(buf) < 1500000:
        chunk = resp.read(4096)
        if not chunk:
            break
        buf.extend(chunk)
        a = buf.find(b"\xff\xd8")
        b = buf.find(b"\xff\xd9", a + 2) if a != -1 else -1
        if a != -1 and b != -1:
            frame = bytes(buf[a : b + 2])
            dt = round((time.time() - t0) * 1000, 1)
            print(f"STREAM FRAME GRABBED! {len(frame)} bytes in {dt} ms")
            with open("/userdata/agent/run/camera_shot.jpg", "wb") as f:
                f.write(frame)
            break
