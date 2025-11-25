import cv2
from perception.vision.gesture_detector import GestureProcessor

def main() -> None:
    gp = GestureProcessor(detection_interval_ms=200, min_confidence=0.5)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open camera")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gesture = gp.process_frame(frame)
            if gesture:
                print("Gesture:", gesture)
                # Draw gesture label on the preview window
                cv2.putText(
                    frame,
                    f"Gesture: {gesture}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Gesture Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()