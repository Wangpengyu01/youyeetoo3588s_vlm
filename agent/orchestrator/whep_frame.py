"""Single-frame grab from MediaMTX WHEP (WebRTC) using GStreamer webrtcbin + gi."""
from __future__ import annotations

import logging
import threading
import urllib.request
from pathlib import Path

LOG = logging.getLogger(__name__)


def _whep_post(whep_url: str, offer_sdp: str, timeout: float) -> str:
    req = urllib.request.Request(
        whep_url,
        data=offer_sdp.encode("utf-8"),
        headers={"Content-Type": "application/sdp"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def grab_whep_frame_gst(
    whep_url: str,
    save_path: Path,
    *,
    timeout: float = 12.0,
    size: int = 448,
) -> bool:
    import gi

    gi.require_version("Gst", "1.0")
    gi.require_version("GstWebRTC", "1.0")
    gi.require_version("GstSdp", "1.0")
    from gi.repository import GLib, Gst, GstSdp, GstWebRTC

    Gst.init(None)
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = save_path.with_suffix(".whep_tmp.jpg")

    state: dict = {
        "done": False,
        "ok": False,
        "whep_url": whep_url,
        "timeout": timeout,
    }

    def finish(success: bool) -> None:
        if state["done"]:
            return
        state["done"] = True
        state["ok"] = success
        loop.quit()

    def on_bus(_bus, message, _data):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, _ = message.parse_error()
            LOG.warning("[whep] gst error: %s", err)
            finish(False)
        elif t == Gst.MessageType.EOS:
            finish(state.get("file_ok", False))

    def link_decode_branch(_webrtcbin, pad, _user_data):
        if state.get("linked"):
            return
        caps = pad.get_current_caps()
        if not caps:
            return
        struct = caps.get_structure(0)
        if struct.get_string("media") != "video":
            return
        depay = Gst.ElementFactory.make("rtph264depay", "depay")
        parse = Gst.ElementFactory.make("h264parse", "parse")
        dec = Gst.ElementFactory.make("mppvideodec", "dec")
        if not dec:
            dec = Gst.ElementFactory.make("avdec_h264", "dec")
        convert = Gst.ElementFactory.make("videoconvert", "convert")
        scale = Gst.ElementFactory.make("videoscale", "scale")
        enc = Gst.ElementFactory.make("jpegenc", "enc")
        enc.set_property("quality", 90)
        sink = Gst.ElementFactory.make("filesink", "sink")
        sink.set_property("location", str(tmp))
        sink.set_property("sync", False)
        sink.set_property("async", False)
        for el in (depay, parse, dec, convert, scale, enc, sink):
            pipeline.add(el)
        if not depay.link(parse) or not parse.link(dec) or not dec.link(convert):
            finish(False)
            return
        capsfilter = Gst.ElementFactory.make("capsfilter", "scale_caps")
        capsfilter.set_property(
            "caps", Gst.Caps.from_string(f"video/x-raw,width={size},height={size}")
        )
        pipeline.add(capsfilter)
        if not convert.link(scale) or not scale.link(capsfilter) or not capsfilter.link(enc) or not enc.link(sink):
            finish(False)
            return
        for el in (depay, parse, dec, convert, scale, capsfilter, enc, sink):
            el.sync_state_with_parent()
        sink_pad = depay.get_static_pad("sink")
        if sink_pad and pad.link(sink_pad) == Gst.PadLinkReturn.OK:
            state["linked"] = True
            LOG.info("[whep] linked H264 decode → %s", tmp)

    def on_negotiation_needed(webrtcbin):
        def on_offer_created(promise, _element, __):
            promise.wait()
            reply = promise.get_reply()
            offer = reply.get_value("offer")
            webrtcbin.emit("set-local-description", offer, Gst.Promise.new())
            offer_sdp = offer.sdp.as_text()
            try:
                answer_sdp = _whep_post(state["whep_url"], offer_sdp, state["timeout"])
            except Exception as exc:
                LOG.warning("[whep] POST failed: %s", exc)
                finish(False)
                return
            res, sdp_msg = GstSdp.SDPMessage.new()
            GstSdp.sdp_message_parse_buffer(answer_sdp.encode("utf-8"), sdp_msg)
            answer = GstWebRTC.WebRTCSessionDescription.new(
                GstWebRTC.WebRTCSDPType.ANSWER, sdp_msg
            )
            webrtcbin.emit("set-remote-description", answer, Gst.Promise.new())

        promise = Gst.Promise.new_with_change_func(on_offer_created, webrtcbin, None)
        webrtcbin.emit("create-offer", None, promise)

    pipeline = Gst.Pipeline.new("whep-grab")
    if not Gst.ElementFactory.find("nicesrc"):
        LOG.warning(
            "[whep] libnice missing — on board run: sudo bash /userdata/agent/scripts/install_mediamtx_webrtc_deps.sh"
        )
        return False
    webrtcbin = Gst.ElementFactory.make("webrtcbin", "webrtc")
    if not webrtcbin:
        LOG.warning("[whep] webrtcbin missing")
        return False
    webrtcbin.set_property("bundle-policy", GstWebRTC.WebRTCBundlePolicy.MAX_BUNDLE)
    pipeline.add(webrtcbin)
    webrtcbin.connect("on-negotiation-needed", on_negotiation_needed)
    webrtcbin.connect("pad-added", link_decode_branch)

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_bus, None)

    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)

    def watchdog():
        import time

        time.sleep(timeout)
        if not state["done"]:
            LOG.warning("[whep] timeout %.1fs", timeout)
            finish(False)

    threading.Thread(target=watchdog, daemon=True).start()

    def poll_file():
        import time

        for _ in range(int(timeout * 10)):
            if state["done"]:
                return
            if tmp.is_file() and tmp.stat().st_size > 1000:
                state["file_ok"] = True
                tmp.replace(save_path)
                LOG.info("[whep] frame saved %s (%d bytes)", save_path, save_path.stat().st_size)
                finish(True)
                return
            time.sleep(0.1)
        if not state["done"]:
            finish(False)

    threading.Thread(target=poll_file, daemon=True).start()

    try:
        loop.run()
    finally:
        pipeline.set_state(Gst.State.NULL)

    if state["ok"] and save_path.is_file():
        return True
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    return False
