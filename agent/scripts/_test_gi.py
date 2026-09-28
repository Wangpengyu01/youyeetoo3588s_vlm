import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst
Gst.init(None)
print("gi+GstWebRTC ok")
