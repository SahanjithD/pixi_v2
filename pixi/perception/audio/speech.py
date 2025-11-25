from __future__ import annotations

import json
import math
import time
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from vosk import KaldiRecognizer, Model
except ImportError:
    Model = None
    KaldiRecognizer = None

try:
    from pvrecorder import PvRecorder
except ImportError:
    PvRecorder = None


class SpeechCaptureError(RuntimeError):
    """Raised when an audio capture or transcription step fails."""


@dataclass(slots=True)
class SpeechCaptureConfig:
    """Configuration for recording speech after a wake word."""
    device_index: int = -1
    sample_rate: int = 16000
    frame_length: int = 512
    max_duration: float = 4.5
    min_duration: float = 0.35
    silence_timeout: float = 0.8
    silence_threshold: float = 550.0


class SpeechRecorder:
    """Utility that records PCM audio using PvRecorder until silence or max duration."""

    def __init__(self, config: SpeechCaptureConfig) -> None:
        if PvRecorder is None:
            raise SpeechCaptureError("Speech recording requires `pvrecorder`.")
        self._config = config

    def capture(self) -> bytes:
        cfg = self._config
        recorder = PvRecorder(device_index=cfg.device_index, frame_length=cfg.frame_length)
        frames: list[array] = []
        start_time = time.time()
        silence_start: Optional[float] = None

        print("[Speech] Recording...")
        try:
            recorder.start()
            while True:
                pcm = recorder.read()
                frame = array("h", pcm)
                frames.append(frame)

                elapsed = time.time() - start_time
                if elapsed >= cfg.max_duration:
                    break

                # Silence Detection Logic
                energy = math.sqrt(sum(x * x for x in pcm) / len(pcm))
                if energy >= cfg.silence_threshold:
                    silence_start = None
                else:
                    if elapsed >= cfg.min_duration:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= cfg.silence_timeout:
                            break
        except Exception as e:
            print(f"[Speech] Capture error: {e}")
        finally:
            recorder.stop()
            recorder.delete()

        if not frames:
            return b""

        # Flatten frames to bytes
        buffer = array("h")
        for f in frames:
            buffer.extend(f)
        return buffer.tobytes()


class VoskSpeechRecognizer:
    """Wrapper around Vosk to transcribe PCM16 audio buffers."""

    def __init__(self, model_path: Path) -> None:
        if Model is None:
            raise SpeechCaptureError("Transcription requires `vosk`.")
        
        if not model_path.exists():
             raise FileNotFoundError(f"Vosk model path not found: {model_path}")
             
        # Resolve to the inner folder if needed (where 'conf/model.conf' lives)
        resolved = self._resolve_model_dir(model_path)
        if not resolved:
             raise ValueError(f"Could not find 'conf/model.conf' inside {model_path}")
             
        self._model = Model(str(resolved))
        self._sample_rate = 16000

    def _resolve_model_dir(self, path: Path) -> Optional[Path]:
        if (path / "conf" / "model.conf").exists():
            return path
        # Search subdirectories
        for p in path.rglob("model.conf"):
            return p.parent.parent
        return None

    def transcribe_text(self, pcm_bytes: bytes) -> str:
        rec = KaldiRecognizer(self._model, self._sample_rate)
        rec.SetWords(True)
        rec.AcceptWaveform(pcm_bytes)
        res = json.loads(rec.FinalResult())
        return res.get("text", "").strip()