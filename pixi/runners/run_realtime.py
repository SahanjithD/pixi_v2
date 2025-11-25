from __future__ import annotations

import argparse
import time
import cv2
import sys
from pathlib import Path

# --- CORE IMPORTS ---
from pixi.core.state_manager import StateManager
from pixi.core.local_brain import LocalBrain
from pixi.core.reasoning_engine import ReasoningEngine
from pixi.core.actions import ACTION_REGISTRY, ActionName, attach_stub_handlers
from pixi.perception.audio.hotword import HotwordDetector

# --- AUDIO IMPORTS ---
from pixi.perception.audio.speech import SpeechRecorder, SpeechCaptureConfig, VoskSpeechRecognizer

def main(
    camera_index: int = 0,
    enable_audio: bool = True,
    show_preview: bool = False
) -> None:
    print("[Pixi] Booting up System...")

    # 1. Initialize Core Systems
    state = StateManager()
    
    try:
        # Local Brain (Fast / Utility AI)
        brain = LocalBrain(state_manager=state)
        
        # Cloud Brain (Slow / LLM) - Only initialized if audio enabled
        llm_engine = ReasoningEngine(state_manager=state) if enable_audio else None
    except Exception as e:
        print(f"[Pixi] Critical Error initializing Brains: {e}")
        return
    
    # 2. Initialize Hardware Stubs
    attach_stub_handlers(state_manager=state)
    print("[Pixi] Hardware Drivers: STUBBED (Simulation Mode)")

    # 3. Initialize Audio Systems
    hotword: HotwordDetector | None = None
    recorder: SpeechRecorder | None = None
    recognizer: VoskSpeechRecognizer | None = None

    if enable_audio:
        try:
            # A. Wake Word (Porcupine)
            hotword = HotwordDetector(access_key=None) # Env Var PICOVOICE_ACCESS_KEY
            hotword.start()
            
            # B. Speech Recorder (PvRecorder)
            rec_config = SpeechCaptureConfig(silence_threshold=500.0)
            recorder = SpeechRecorder(rec_config)
            
            # C. Speech-to-Text (Vosk)
            # Find model automatically in pixi/models/audio/
            root_dir = Path(__file__).resolve().parent.parent
            model_dir = root_dir / "models" / "audio"
            vosk_folders = list(model_dir.glob("vosk-model*"))
            
            if vosk_folders:
                print(f"[Pixi] Loading Vosk Model: {vosk_folders[0].name}")
                recognizer = VoskSpeechRecognizer(model_path=vosk_folders[0])
            else:
                print("[Pixi] Warning: No Vosk model found. Voice commands disabled.")
                recognizer = None

            print("[Pixi] Ears: ON (Listening for 'Pixi')")
        except Exception as e:
            print(f"[Pixi] Ears: OFF (Error: {e})")
            print("[Pixi] Hint: Check PICOVOICE_ACCESS_KEY and model paths.")

    # 4. Initialize Vision
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    if not cap.isOpened():
        print(f"[Pixi] Critical Error: Camera {camera_index} not found.")
        if hotword: hotword.close()
        return

    print("[Pixi] System Online. Starting Life Loop...")
    
    # --- THE FAST LOOP (30Hz) ---
    try:
        while True:
            loop_start = time.time()

            # A. SENSE (Vision)
            ret, frame = cap.read()
            if not ret:
                print("[Pixi] Camera lost.")
                break

            # B. SENSE (Audio & Touch)
            is_listening = False
            
            # Check Hotword
            if hotword:
                events = hotword.drain_events()
                if any(e.summary == "hotword_detected" for e in events):
                    print("\n[Pixi] ! HEARD WAKE WORD !")
                    
                    # --- AUDIO INTERRUPT SEQUENCE ---
                    
                    # 1. Freeze Motors (Dispatch LISTEN action)
                    # We bypass the local brain loop to ensure immediate reaction
                    if ACTION_REGISTRY.get(ActionName.LISTEN_TO_USER):
                        ACTION_REGISTRY.get(ActionName.LISTEN_TO_USER).dispatch()
                    
                    # 2. Record & Transcribe (Blocking)
                    if recorder and recognizer and llm_engine:
                        try:
                            print("[Pixi] Listening for command...")
                            audio_data = recorder.capture()
                            user_text = recognizer.transcribe_text(audio_data)
                            
                            if user_text:
                                print(f"[User] '{user_text}'")
                                print("[Pixi] Thinking (LLM)...")
                                
                                # 3. LLM Decision (Action Only)
                                action_response = llm_engine.decide_action_from_text(user_text)
                                print(f"[Pixi] Emotion Response: {action_response.value}")
                                
                                # 4. Execute Emotion
                                descriptor = ACTION_REGISTRY.get(action_response)
                                if descriptor:
                                    descriptor.dispatch()
                                    
                                # Pause briefly to let the emotion play out
                                time.sleep(2.0)
                            else:
                                print("[Pixi] Heard silence.")
                        except Exception as e:
                            print(f"[Pixi] Audio Processing Error: {e}")
                    
                    # Resume normal loop
                    is_listening = False

            # Placeholder for Touch
            is_touching = False 

            # C. THINK (Utility AI)
            # Only run if we aren't currently processing a voice command
            decision = brain.decide(
                frame=frame, 
                is_listening=is_listening, 
                is_touching=is_touching
            )

            # D. ACT (Dispatch)
            action_name = decision["action"]
            
            # Dispatch action to hardware
            action_desc = ACTION_REGISTRY.get(action_name)
            if action_desc:
                action_desc.dispatch(
                    face_data=decision.get("face_data"), 
                    gesture=decision.get("gesture")
                )
            
            # OPTIONAL: Preview
            if show_preview:
                display_frame = frame.copy()
                
                # Draw Face Target
                face = decision.get("face_data")
                if face:
                    h, w, _ = display_frame.shape
                    cx, cy = int(face["center_x"] * w), int(face["center_y"] * h)
                    
                    # Draw Bounding Box
                    # Use normalized width/height if available (added in recent update), else fallback to px
                    if "width" in face:
                        box_w = int(face["width"] * w)
                        box_h = int(face["height"] * h)
                    else:
                        # Fallback for older version compatibility
                        box_w = int(face.get("width_px", 0))
                        box_h = int(face.get("height_px", 0))

                    if box_w > 0 and box_h > 0:
                        x1 = int(cx - box_w / 2)
                        y1 = int(cy - box_h / 2)
                        cv2.rectangle(display_frame, (x1, y1), (x1 + box_w, y1 + box_h), (0, 255, 0), 2)
                        
                        # Show Area Percentage
                        area_pct = face.get("area", 0.0) * 100
                        cv2.putText(display_frame, f"Area: {area_pct:.1f}%", (x1, y1 - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                    cv2.circle(display_frame, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.putText(display_frame, "Face", (cx + 15, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                # Draw Gesture
                gesture = decision.get("gesture")
                if gesture:
                    cv2.putText(display_frame, f"Gesture: {gesture}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                # Draw Action
                cv2.putText(display_frame, f"Action: {action_name.value}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                cv2.imshow("Pixi Vision", display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # E. RATE LIMIT
            elapsed = time.time() - loop_start
            time.sleep(max(0.0, 0.033 - elapsed))

    except KeyboardInterrupt:
        print("\n[Pixi] Shutting down...")
    finally:
        cap.release()
        if show_preview:
            cv2.destroyAllWindows()
        if hotword:
            hotword.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--no-audio", action="store_false", dest="enable_audio", help="Disable audio features")
    parser.add_argument("--preview", action="store_true", help="Show camera preview window")
    args = parser.parse_args()
    
    main(
        camera_index=args.camera_index,
        enable_audio=args.enable_audio,
        show_preview=args.preview
    )