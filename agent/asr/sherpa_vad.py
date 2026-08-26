"""Silero VAD via sherpa-onnx C API (ctypes) — no Python sherpa_onnx wheel required."""
from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path


class SherpaVadError(RuntimeError):
    pass


class _SileroVadModelConfig(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char_p),
        ("threshold", ctypes.c_float),
        ("min_silence_duration", ctypes.c_float),
        ("min_speech_duration", ctypes.c_float),
        ("window_size", ctypes.c_int32),
        ("max_speech_duration", ctypes.c_float),
    ]


class _TenVadModelConfig(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_char_p),
        ("threshold", ctypes.c_float),
        ("min_silence_duration", ctypes.c_float),
        ("min_speech_duration", ctypes.c_float),
        ("window_size", ctypes.c_int32),
        ("max_speech_duration", ctypes.c_float),
    ]


class _VadModelConfig(ctypes.Structure):
    _fields_ = [
        ("silero_vad", _SileroVadModelConfig),
        ("sample_rate", ctypes.c_int32),
        ("num_threads", ctypes.c_int32),
        ("provider", ctypes.c_char_p),
        ("debug", ctypes.c_int32),
        ("ten_vad", _TenVadModelConfig),
    ]


class _SpeechSegment(ctypes.Structure):
    _fields_ = [
        ("start", ctypes.c_int32),
        ("samples", ctypes.POINTER(ctypes.c_float)),
        ("n", ctypes.c_int32),
    ]


@dataclass
class SpeechSegment:
    start: int
    samples: list[float]

    @property
    def duration_sec(self) -> float:
        return len(self.samples) / 16000.0


def _load_library(lib_dir: str) -> ctypes.CDLL:
    lib_dir = str(Path(lib_dir).resolve())
    os.environ["LD_LIBRARY_PATH"] = lib_dir + (
        f":{os.environ['LD_LIBRARY_PATH']}" if os.environ.get("LD_LIBRARY_PATH") else ""
    )
    path = Path(lib_dir) / "libsherpa-onnx-c-api.so"
    if not path.is_file():
        raise SherpaVadError(f"missing {path}")
    return ctypes.CDLL(str(path))


class SherpaVad:
    """Streaming Silero VAD wrapper."""

    def __init__(
        self,
        model_path: str,
        lib_dir: str,
        *,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_silence_duration: float = 0.4,
        min_speech_duration: float = 0.25,
        max_speech_duration: float = 30.0,
        window_size: int = 512,
        num_threads: int = 1,
        buffer_seconds: float = 30.0,
    ) -> None:
        model_path = str(Path(model_path).resolve())
        if not Path(model_path).is_file():
            raise SherpaVadError(f"VAD model not found: {model_path}")

        self._lib = _load_library(lib_dir)
        self._sample_rate = sample_rate

        create = self._lib.SherpaOnnxCreateVoiceActivityDetector
        create.argtypes = [ctypes.POINTER(_VadModelConfig), ctypes.c_float]
        create.restype = ctypes.c_void_p

        destroy = self._lib.SherpaOnnxDestroyVoiceActivityDetector
        destroy.argtypes = [ctypes.c_void_p]
        destroy.restype = None

        accept = self._lib.SherpaOnnxVoiceActivityDetectorAcceptWaveform
        accept.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int32]
        accept.restype = None

        empty = self._lib.SherpaOnnxVoiceActivityDetectorEmpty
        empty.argtypes = [ctypes.c_void_p]
        empty.restype = ctypes.c_int32

        detected = self._lib.SherpaOnnxVoiceActivityDetectorDetected
        detected.argtypes = [ctypes.c_void_p]
        detected.restype = ctypes.c_int32

        front = self._lib.SherpaOnnxVoiceActivityDetectorFront
        front.argtypes = [ctypes.c_void_p]
        front.restype = ctypes.POINTER(_SpeechSegment)

        pop = self._lib.SherpaOnnxVoiceActivityDetectorPop
        pop.argtypes = [ctypes.c_void_p]
        pop.restype = None

        flush_fn = self._lib.SherpaOnnxVoiceActivityDetectorFlush
        flush_fn.argtypes = [ctypes.c_void_p]
        flush_fn.restype = None

        destroy_seg = self._lib.SherpaOnnxDestroySpeechSegment
        destroy_seg.argtypes = [ctypes.POINTER(_SpeechSegment)]
        destroy_seg.restype = None

        cfg = _VadModelConfig()
        ctypes.memset(ctypes.byref(cfg), 0, ctypes.sizeof(cfg))
        cfg.silero_vad.model = model_path.encode("utf-8")
        cfg.silero_vad.threshold = threshold
        cfg.silero_vad.min_silence_duration = min_silence_duration
        cfg.silero_vad.min_speech_duration = min_speech_duration
        cfg.silero_vad.max_speech_duration = max_speech_duration
        cfg.silero_vad.window_size = window_size
        cfg.sample_rate = sample_rate
        cfg.num_threads = num_threads
        cfg.provider = b"cpu"
        cfg.debug = 0

        handle = create(ctypes.byref(cfg), float(buffer_seconds))
        if not handle:
            raise SherpaVadError("SherpaOnnxCreateVoiceActivityDetector returned NULL")

        self._handle = handle
        self._destroy = destroy
        self._accept = accept
        self._empty = empty
        self._detected = detected
        self._front = front
        self._pop = pop
        self._flush = flush_fn
        self._destroy_seg = destroy_seg
        self._speaking = False

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._destroy(self._handle)
            self._handle = None  # type: ignore[assignment]

    def __enter__(self) -> SherpaVad:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def is_speech_detected(self) -> bool:
        return bool(self._detected(self._handle))

    def accept_pcm_float32(self, samples: list[float]) -> None:
        if not samples:
            return
        buf = (ctypes.c_float * len(samples))(*samples)
        self._accept(self._handle, buf, len(samples))

    def flush(self) -> None:
        self._flush(self._handle)

    def poll_segments(self) -> list[tuple[str, SpeechSegment | None]]:
        """Return edge events and completed segments since last call."""
        events: list[tuple[str, SpeechSegment | None]] = []
        now = self.is_speech_detected
        if now and not self._speaking:
            events.append(("speech_start", None))
        elif not now and self._speaking:
            events.append(("speech_end", None))
        self._speaking = now

        while not self._empty(self._handle):
            seg_ptr = self._front(self._handle)
            if not seg_ptr:
                break
            seg = seg_ptr.contents
            samples = [seg.samples[i] for i in range(seg.n)]
            events.append(
                (
                    "segment",
                    SpeechSegment(start=seg.start, samples=samples),
                )
            )
            self._destroy_seg(seg_ptr)
            self._pop(self._handle)
        return events
