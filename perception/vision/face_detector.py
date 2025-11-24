import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Iterable, Tuple, Optional

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite


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

        current_dir = Path(__file__).resolve().parent
        model_path = current_dir.parent.parent / "models" / "vision" / "blaze_face_short_range.tflite"

        if not model_path.exists():
            raise FileNotFoundError(f"Face model not found at {model_path}")

        self._interpreter = tflite.Interpreter(model_path=str(model_path))
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

    def process_frame(self, frame: np.ndarray) -> List[VisionEvent]:
        if frame.shape[1] != self._frame_width or frame.shape[0] != self._frame_height:
            frame = cv2.resize(frame, (self._frame_width, self._frame_height), interpolation=cv2.INTER_LINEAR)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        detections = self._run_tflite(rgb)
        events = self._extract_faces(detections, frame.shape)
        return events

    def _run_tflite(self, rgb: np.ndarray) -> Iterable[Tuple[float, float, float, float, float]]:
        """Return iterable of (score, xmin, ymin, width, height) in absolute pixels."""
        # BlazeFace expects 128x128 or 256x256; adjust as needed:
        h, w, _ = rgb.shape
        input_h = self._input_details[0]["shape"][1]
        input_w = self._input_details[0]["shape"][2]
        resized = cv2.resize(rgb, (input_w, input_h))
        input_tensor = np.expand_dims(resized.astype(np.float32) / 255.0, axis=0)

        self._interpreter.set_tensor(self._input_details[0]["index"], input_tensor)
        self._interpreter.invoke()

        # NOTE: Exact output format depends on the specific BlazeFace model.
        # Below is a typical pattern; you may need to adapt indices/order:
        scores = self._interpreter.get_tensor(self._output_details[0]["index"])[0]
        boxes = self._interpreter.get_tensor(self._output_details[1]["index"])[0]

        detections = []
        for score, box in zip(scores, boxes):
            if score < self._min_face_confidence:
                continue
            ymin, xmin, ymax, xmax = box  # if normalized [0,1]; adjust if not
            xmin_px = xmin * w
            ymin_px = ymin * h
            width_px = (xmax - xmin) * w
            height_px = (ymax - ymin) * h
            detections.append((float(score), xmin_px, ymin_px, width_px, height_px))
        return detections

    def _extract_faces(
        self,
        detections: Iterable[Tuple[float, float, float, float, float]],
        shape: Tuple[int, int, int],
    ) -> List[VisionEvent]:
        events: List[VisionEvent] = []
        h, w, _ = shape

        for score, xmin, ymin, width_px, height_px in detections:
            cx = (xmin + width_px / 2) / w
            cy = (ymin + height_px / 2) / h
            area = (width_px * height_px) / (w * h)

            events.append(
                VisionEvent(
                    summary="face_detected",
                    weight=score,
                    data={
                        "type": "face",
                        "center_x": cx,
                        "center_y": cy,
                        "area": area,
                        "confidence": score,
                    },
                )
            )
        return events