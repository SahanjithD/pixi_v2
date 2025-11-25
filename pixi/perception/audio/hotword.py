from __future__ import annotations

import os
import threading
import time
import queue
from dataclasses import dataclass
from typing import List, Optional, Sequence

try:
    import pvporcupine
    from pvrecorder import PvRecorder
except ImportError:
    PvRecorder = None
    pvporcupine = None


@dataclass(slots=True)
class AudioEvent:
    """Structured audio event similar to VisionEvent."""
    summary: str
    data: dict


class HotwordDetector:
    """
    Background thread that listens for wake words using Porcupine.
    Usage:
      detector = HotwordDetector()
      detector.start()
      ...
      events = detector.drain_events()
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        keyword_paths: Optional[List[str]] = None,
        sensitivities: Optional[List[float]] = None,
        device_index: int = -1,
    ) -> None:
        if pvporcupine is None or PvRecorder is None:
            raise ImportError("Missing dependencies. Run: pip install pvporcupine pvrecorder")

        self._key = access_key or os.environ.get("PICOVOICE_ACCESS_KEY")
        if not self._key:
            raise ValueError("No Access Key provided. Set PICOVOICE_ACCESS_KEY env var.")

        self._keywords = keywords or ["picovoice"]  # Default built-in keyword
        self._keyword_paths = keyword_paths
        self._sensitivities = sensitivities
        self._device_index = device_index
        
        self._porcupine = None
        self._recorder = None
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._event_queue: queue.Queue[AudioEvent] = queue.Queue()

        self._init_porcupine()

    def _init_porcupine(self) -> None:
        try:
            self._porcupine = pvporcupine.create(
                access_key=self._key,
                keywords=self._keywords,
                keyword_paths=self._keyword_paths,
                sensitivities=self._sensitivities
            )
            self._recorder = PvRecorder(
                device_index=self._device_index,
                frame_length=self._porcupine.frame_length
            )
        except Exception as e:
            print(f"[Hotword] Failed to init Porcupine: {e}")
            raise

    def start(self) -> None:
        """Starts the listening thread."""
        if self._is_running:
            return
        
        self._is_running = True
        self._recorder.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        print(f"[Hotword] Listening for {self._keywords}...")
        try:
            while self._is_running:
                pcm = self._recorder.read()
                keyword_index = self._porcupine.process(pcm)
                
                if keyword_index >= 0:
                    # Wake word detected!
                    keyword = "unknown"
                    if self._keywords and 0 <= keyword_index < len(self._keywords):
                        keyword = self._keywords[keyword_index]
                    
                    event = AudioEvent(
                        summary="hotword_detected",
                        data={"keyword": keyword, "index": keyword_index}
                    )
                    self._event_queue.put(event)
        except Exception as e:
            print(f"[Hotword] Thread error: {e}")
        finally:
            self._is_running = False

    def drain_events(self) -> List[AudioEvent]:
        """Returns all events accumulated since last call."""
        events = []
        while not self._event_queue.empty():
            events.append(self._event_queue.get_nowait())
        return events

    def close(self) -> None:
        """Stops thread and cleans up resources."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        
        if self._recorder:
            self._recorder.stop()
            self._recorder.delete()
        
        if self._porcupine:
            self._porcupine.delete()