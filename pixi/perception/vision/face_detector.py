from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Iterable, Tuple, Optional

import cv2
import numpy as np
import mediapipe as mp

# Try importing tflite_runtime; if missing, we will force fallback later.
try:
    import tflite_runtime.interpreter as tflite
    _TFLITE_AVAILABLE = True
except ImportError:
    _TFLITE_AVAILABLE = False


@dataclass(slots=True)
class VisionEvent:
    summary: str
    weight: float
    data: Dict[str, float | str | bool | Dict[str, float]]


class VisionProcessor:
    def __init__(
        self,
        *,
        min_face_confidence: float = 0.5,
        camera_index: int = 0,
        frame_width: int = 320,
        frame_height: int = 240,
    ) -> None:
        self._camera_index = camera_index
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._min_face_confidence = min_face_confidence
        
        self._use_tflite = False
        self._interpreter = None
        self._mp_face_detection = None

        # ---------------------------------------------------------
        # STRATEGY 1: Try TFLite Runtime (Lightweight)
        # ---------------------------------------------------------
        if _TFLITE_AVAILABLE:
            try:
                current_dir = Path(__file__).resolve().parent
                # Adjust path to where your model actually lives relative to this file
                model_path = current_dir.parent.parent / "models" / "vision" / "blaze_face_short_range.tflite"

                if not model_path.exists():
                    print(f"[Vision] TFLite model not found at {model_path}. Skipping.")
                    raise FileNotFoundError("Model file missing")

                self._interpreter = tflite.Interpreter(model_path=str(model_path))
                self._interpreter.allocate_tensors()
                self._input_details = self._interpreter.get_input_details()
                self._output_details = self._interpreter.get_output_details()
                self._use_tflite = True
                print("[Vision] Face Detection: Running on TFLite Runtime (Fast Path).")
            except Exception as e:
                print(f"[Vision] TFLite initialization failed: {e}")
                self._use_tflite = False

        # ---------------------------------------------------------
        # STRATEGY 2: Fallback to MediaPipe (Robust)
        # ---------------------------------------------------------
        if not self._use_tflite:
            print("[Vision] Face Detection: Falling back to MediaPipe Solutions.")
            self._mp_face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,  # 0 = Short Range (2m), 1 = Full Range
                min_detection_confidence=min_face_confidence
            )

    def process_frame(self, frame: np.ndarray) -> List[VisionEvent]:
        # Resize for performance if raw frame is huge
        if frame.shape[1] != self._frame_width or frame.shape[0] != self._frame_height:
            frame = cv2.resize(frame, (self._frame_width, self._frame_height), interpolation=cv2.INTER_LINEAR)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Branch based on which engine loaded successfully
        if self._use_tflite:
            detections = self._run_tflite(rgb)
        else:
            detections = self._run_mediapipe(rgb)

        events = self._extract_faces(detections, frame.shape)
        return events

    def _run_tflite(self, rgb: np.ndarray) -> Iterable[Tuple[float, float, float, float, float]]:
        """
        Executes the custom TFLite model.
        Returns: Iterable of (score, xmin_px, ymin_px, width_px, height_px)
        """
        h, w, _ = rgb.shape
        
        # Get model input shape (usually 128x128 for BlazeFace)
        input_h = self._input_details[0]["shape"][1]
        input_w = self._input_details[0]["shape"][2]
        
        # Prepare tensor
        resized = cv2.resize(rgb, (input_w, input_h))
        # Normalize to [-1, 1] or [0, 1] depending on model training. 
        # Standard BlazeFace often expects [-1, 1], but check your specific .tflite metadata.
        # Here assuming standard [0, 255] -> float [-1, 1] or [0, 1]
        input_tensor = np.expand_dims((resized.astype(np.float32) / 127.5) - 1.0, axis=0)

        self._interpreter.set_tensor(self._input_details[0]["index"], input_tensor)
        self._interpreter.invoke()

        # NOTE: Output tensor indices vary by model export. 
        # Standard BlazeFace: [0] = regressors (boxes), [1] = classificators (scores)
        # You might need to swap these indices if your specific .tflite is different.
        raw_boxes = self._interpreter.get_tensor(self._output_details[0]["index"])[0]
        raw_scores = self._interpreter.get_tensor(self._output_details[1]["index"])[0]

        detections = []
        # BlazeFace anchors logic is complex to implement manually (decoding offsets).
        # IF your .tflite outputs raw decoded boxes (ymin, xmin, ymax, xmax), use this loop:
        # If it outputs encoded anchors, this loop will be incorrect without an SSD decoder.
        
        # Assuming TFLite output is pre-decoded (like MediaPipe Tasks):
        for i, score_val in enumerate(raw_scores):
            # Verify score shape (BlazeFace sometimes outputs [896, 1])
            score = float(score_val[0]) if isinstance(score_val, (list, np.ndarray)) else float(score_val)
            
            if score < self._min_face_confidence:
                continue
                
            box = raw_boxes[i]
            # Typical box format: [ymin, xmin, ymax, xmax] normalized
            ymin, xmin, ymax, xmax = box[0], box[1], box[2], box[3]
            
            xmin_px = xmin * w
            ymin_px = ymin * h
            width_px = (xmax - xmin) * w
            height_px = (ymax - ymin) * h
            
            detections.append((score, xmin_px, ymin_px, width_px, height_px))
            
        return detections

    def _run_mediapipe(self, rgb: np.ndarray) -> Iterable[Tuple[float, float, float, float, float]]:
        """
        Executes the fallback MediaPipe Solutions model.
        Returns: Iterable of (score, xmin_px, ymin_px, width_px, height_px)
        """
        results = self._mp_face_detection.process(rgb)
        
        if not results.detections:
            return []

        h, w, _ = rgb.shape
        formatted_detections = []

        for det in results.detections:
            score = det.score[0]
            bbox = det.location_data.relative_bounding_box
            
            xmin_px = bbox.xmin * w
            ymin_px = bbox.ymin * h
            width_px = bbox.width * w
            height_px = bbox.height * h
            
            formatted_detections.append((score, xmin_px, ymin_px, width_px, height_px))
            
        return formatted_detections

    def _extract_faces(
        self,
        detections: Iterable[Tuple[float, float, float, float, float]],
        shape: Tuple[int, int, int],
    ) -> List[VisionEvent]:
        events: List[VisionEvent] = []
        h, w, _ = shape

        for score, xmin_px, ymin_px, width_px, height_px in detections:
            # Calculate normalized centers for the logic engine
            cx = (xmin_px + width_px / 2) / w
            cy = (ymin_px + height_px / 2) / h
            area = (width_px * height_px) / (w * h)

            events.append(
                VisionEvent(
                    summary="face_detected",
                    weight=score,
                    data={
                        "type": "face",
                        "center_x": max(0.0, min(1.0, cx)),
                        "center_y": max(0.0, min(1.0, cy)),
                        "area": area,
                        "confidence": score,
                        "width_px": width_px,
                        "height_px": height_px
                    },
                )
            )
        return events