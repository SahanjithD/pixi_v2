from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, List

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class GestureProcessor:
    """
    Detects hand gestures (Wave, Thumb_Up, Closed_Fist, etc.)
    Optimized for Raspberry Pi: Runs inference only every N milliseconds.
    """

    def __init__(
        self,
        *,
        detection_interval_ms: int = 500,  # Check gestures 2 times/sec (saves CPU)
        min_confidence: float = 0.5
    ) -> None:
        self._last_run_time = 0
        self._interval_ms = detection_interval_ms
        self._current_gesture: Optional[str] = None
        
        # ---------------------------------------------------------------------
        # 1. Load Model from the NEW structure
        # ---------------------------------------------------------------------
        current_dir = Path(__file__).resolve().parent
        # Path: pixi/models/vision/gesture_recognizer.task
        model_path = current_dir.parent.parent / "models" / "vision" / "gesture_recognizer.task"

        if not model_path.exists():
            raise FileNotFoundError(f"Gesture model not found at: {model_path}")

        # 2. Initialize MediaPipe Gesture Recognizer
        # Load model content directly to avoid path parsing issues on some platforms
        with open(model_path, "rb") as f:
            model_content = f.read()

        base_options = python.BaseOptions(model_asset_buffer=model_content)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            min_hand_detection_confidence=min_confidence,
            min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
            # We use IMAGE mode for flexibility in the main loop
            running_mode=vision.RunningMode.IMAGE 
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        print(f"[Vision] Gesture Recognizer loaded successfully.")

    def process_frame(self, frame: cv2.Mat) -> Optional[str]:
        """
        Returns the name of the gesture (e.g., 'Thumb_Up', 'Open_Palm') or None.
        """
        now = time.time() * 1000  # Current time in ms

        # 3. Rate Limiting (Optimization)
        # If we checked recently, return the LAST known gesture without re-running AI.
        if now - self._last_run_time < self._interval_ms:
            return self._current_gesture

        self._last_run_time = now

        # 4. Prepare Image
        # Convert BGR (OpenCV) to RGB (MediaPipe)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # 5. Run Inference
        try:
            result = self._recognizer.recognize(mp_image)
            
            # Extract first found gesture
            if result.gestures and len(result.gestures) > 0:
                # Result structure is List[List[Category]]
                top_gesture = result.gestures[0][0] 
                
                if top_gesture.category_name != "None":
                    self._current_gesture = top_gesture.category_name
                else:
                    self._current_gesture = None
            else:
                self._current_gesture = None
                
        except Exception as e:
            print(f"[Vision] Gesture Error: {e}")
            self._current_gesture = None

        return self._current_gesture