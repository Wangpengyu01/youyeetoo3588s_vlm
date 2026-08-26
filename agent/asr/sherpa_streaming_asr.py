"""Streaming Paraformer ASR via sherpa-onnx OnlineRecognizer C API."""
from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from pathlib import Path


class SherpaStreamingAsrError(RuntimeError):
    pass


class _OnlineTransducerModelConfig(ctypes.Structure):
    _fields_ = [
        ("encoder", ctypes.c_char_p),
        ("decoder", ctypes.c_char_p),
        ("joiner", ctypes.c_char_p),
    ]


class _OnlineParaformerModelConfig(ctypes.Structure):
    _fields_ = [
        ("encoder", ctypes.c_char_p),
        ("decoder", ctypes.c_char_p),
    ]


class _OnlineZipformer2CtcModelConfig(ctypes.Structure):
    _fields_ = [("model", ctypes.c_char_p)]


class _OnlineNemoCtcModelConfig(ctypes.Structure):
    _fields_ = [("model", ctypes.c_char_p)]


class _OnlineModelConfig(ctypes.Structure):
    _fields_ = [
        ("transducer", _OnlineTransducerModelConfig),
        ("paraformer", _OnlineParaformerModelConfig),
        ("zipformer2_ctc", _OnlineZipformer2CtcModelConfig),
        ("tokens", ctypes.c_char_p),
        ("num_threads", ctypes.c_int32),
        ("debug", ctypes.c_int32),
        ("provider", ctypes.c_char_p),
        ("model_type", ctypes.c_char_p),
        ("modeling_unit", ctypes.c_char_p),
        ("bpe_vocab", ctypes.c_char_p),
        ("tokens_buf", ctypes.c_char_p),
        ("tokens_buf_size", ctypes.c_int32),
        ("nemo_ctc", _OnlineNemoCtcModelConfig),
    ]


class _FeatureConfig(ctypes.Structure):
    _fields_ = [
        ("sample_rate", ctypes.c_int32),
        ("feature_dim", ctypes.c_int32),
    ]


class _OnlineCtcFstDecoderConfig(ctypes.Structure):
    _fields_ = [
        ("graph", ctypes.c_char_p),
        ("max_active", ctypes.c_int32),
    ]


class _HomophoneReplacerConfig(ctypes.Structure):
    _fields_ = [
        ("dict_dir", ctypes.c_char_p),
        ("lexicon", ctypes.c_char_p),
        ("rule_fsts", ctypes.c_char_p),
    ]


class _OnlineRecognizerConfig(ctypes.Structure):
    _fields_ = [
        ("feat_config", _FeatureConfig),
        ("model_config", _OnlineModelConfig),
        ("decoding_method", ctypes.c_char_p),
        ("max_active_paths", ctypes.c_int32),
        ("enable_endpoint", ctypes.c_int32),
        ("rule1_min_trailing_silence", ctypes.c_float),
        ("rule2_min_trailing_silence", ctypes.c_float),
        ("rule3_min_utterance_length", ctypes.c_float),
        ("hotwords_file", ctypes.c_char_p),
        ("hotwords_score", ctypes.c_float),
        ("ctc_fst_decoder_config", _OnlineCtcFstDecoderConfig),
        ("rule_fsts", ctypes.c_char_p),
        ("rule_fars", ctypes.c_char_p),
        ("blank_penalty", ctypes.c_float),
        ("hotwords_buf", ctypes.c_char_p),
        ("hotwords_buf_size", ctypes.c_int32),
        ("hr", _HomophoneReplacerConfig),
    ]


class _OnlineRecognizerResult(ctypes.Structure):
    _fields_ = [
        ("text", ctypes.c_char_p),
        ("tokens", ctypes.c_char_p),
        ("tokens_arr", ctypes.POINTER(ctypes.c_char_p)),
        ("timestamps", ctypes.POINTER(ctypes.c_float)),
        ("count", ctypes.c_int32),
        ("json", ctypes.c_char_p),
    ]


def _load_library(lib_dir: str) -> ctypes.CDLL:
    lib_dir = str(Path(lib_dir).resolve())
    os.environ["LD_LIBRARY_PATH"] = lib_dir + (
        f":{os.environ['LD_LIBRARY_PATH']}" if os.environ.get("LD_LIBRARY_PATH") else ""
    )
    path = Path(lib_dir) / "libsherpa-onnx-c-api.so"
    if not path.is_file():
        raise SherpaStreamingAsrError(f"missing {path}")
    return ctypes.CDLL(str(path))


@dataclass
class StreamingParaformerConfig:
    model_dir: str
    sherpa_lib: str
    encoder: str = "encoder.int8.onnx"
    decoder: str = "decoder.int8.onnx"
    tokens: str = "tokens.txt"
    num_threads: int = 2
    sample_rate: int = 16000
    feature_dim: int = 80


class StreamingParaformerRecognizer:
    """Persistent online Paraformer recognizer — feed PCM chunks, get partial/final text."""

    def __init__(self, cfg: StreamingParaformerConfig) -> None:
        self.cfg = cfg
        self.model_dir = Path(cfg.model_dir)
        self._lib = _load_library(cfg.sherpa_lib)
        self._bind()

        config = _OnlineRecognizerConfig()
        config.feat_config.sample_rate = cfg.sample_rate
        config.feat_config.feature_dim = cfg.feature_dim
        config.model_config.paraformer.encoder = str(self.model_dir / cfg.encoder).encode()
        config.model_config.paraformer.decoder = str(self.model_dir / cfg.decoder).encode()
        config.model_config.tokens = str(self.model_dir / cfg.tokens).encode()
        config.model_config.num_threads = cfg.num_threads
        config.model_config.provider = b"cpu"
        config.decoding_method = b"greedy_search"
        config.enable_endpoint = 0

        self._recognizer = self._lib.SherpaOnnxCreateOnlineRecognizer(ctypes.byref(config))
        if not self._recognizer:
            raise SherpaStreamingAsrError("SherpaOnnxCreateOnlineRecognizer failed")
        self._stream = self._lib.SherpaOnnxCreateOnlineStream(self._recognizer)
        if not self._stream:
            raise SherpaStreamingAsrError("SherpaOnnxCreateOnlineStream failed")

    def _bind(self) -> None:
        L = self._lib
        L.SherpaOnnxCreateOnlineRecognizer.argtypes = [ctypes.POINTER(_OnlineRecognizerConfig)]
        L.SherpaOnnxCreateOnlineRecognizer.restype = ctypes.c_void_p
        L.SherpaOnnxDestroyOnlineRecognizer.argtypes = [ctypes.c_void_p]
        L.SherpaOnnxDestroyOnlineRecognizer.restype = None
        L.SherpaOnnxCreateOnlineStream.argtypes = [ctypes.c_void_p]
        L.SherpaOnnxCreateOnlineStream.restype = ctypes.c_void_p
        L.SherpaOnnxDestroyOnlineStream.argtypes = [ctypes.c_void_p]
        L.SherpaOnnxDestroyOnlineStream.restype = None
        L.SherpaOnnxOnlineStreamReset.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        L.SherpaOnnxOnlineStreamReset.restype = None
        L.SherpaOnnxOnlineStreamAcceptWaveform.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32,
        ]
        L.SherpaOnnxOnlineStreamAcceptWaveform.restype = None
        L.SherpaOnnxOnlineStreamInputFinished.argtypes = [ctypes.c_void_p]
        L.SherpaOnnxOnlineStreamInputFinished.restype = None
        L.SherpaOnnxIsOnlineStreamReady.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        L.SherpaOnnxIsOnlineStreamReady.restype = ctypes.c_int32
        L.SherpaOnnxDecodeOnlineStream.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        L.SherpaOnnxDecodeOnlineStream.restype = None
        L.SherpaOnnxGetOnlineStreamResult.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        L.SherpaOnnxGetOnlineStreamResult.restype = ctypes.POINTER(_OnlineRecognizerResult)
        L.SherpaOnnxDestroyOnlineRecognizerResult.argtypes = [ctypes.POINTER(_OnlineRecognizerResult)]
        L.SherpaOnnxDestroyOnlineRecognizerResult.restype = None

    def reset(self) -> None:
        self._lib.SherpaOnnxOnlineStreamReset(self._recognizer, self._stream)

    def _decode_loop(self) -> str:
        while self._lib.SherpaOnnxIsOnlineStreamReady(self._recognizer, self._stream):
            self._lib.SherpaOnnxDecodeOnlineStream(self._recognizer, self._stream)
        result_ptr = self._lib.SherpaOnnxGetOnlineStreamResult(self._recognizer, self._stream)
        if not result_ptr:
            return ""
        try:
            text = result_ptr.contents.text
            return text.decode("utf-8") if text else ""
        finally:
            self._lib.SherpaOnnxDestroyOnlineRecognizerResult(result_ptr)

    def feed(self, samples: list[float], sample_rate: int | None = None) -> str:
        if not samples:
            return self._decode_loop()
        rate = sample_rate or self.cfg.sample_rate
        arr = (ctypes.c_float * len(samples))(*samples)
        self._lib.SherpaOnnxOnlineStreamAcceptWaveform(
            self._stream, rate, arr, len(samples)
        )
        return self._decode_loop()

    def finalize(self) -> str:
        self._lib.SherpaOnnxOnlineStreamInputFinished(self._stream)
        return self._decode_loop()

    def close(self) -> None:
        if self._stream:
            self._lib.SherpaOnnxDestroyOnlineStream(self._stream)
            self._stream = None
        if self._recognizer:
            self._lib.SherpaOnnxDestroyOnlineRecognizer(self._recognizer)
            self._recognizer = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
