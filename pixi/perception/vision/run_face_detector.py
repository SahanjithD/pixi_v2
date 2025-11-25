import cv2

from perception.vision.face_detector import VisionProcessor


def main() -> None:
    vp = VisionProcessor()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[Vision] ERROR: Could not open camera 0")
        return

    print("[Vision] Press 'q' in the window or Ctrl+C in the terminal to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[Vision] WARNING: Failed to read frame from camera")
                break

            events = vp.process_frame(frame)
            if events:
                print(events)

            # Show the frame so you can see the camera feed (optional)
            cv2.imshow("Face Detector", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
