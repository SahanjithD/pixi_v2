from __future__ import annotations

import time
from typing import Dict, Optional, Any

import cv2
import numpy as np

from pixi.core.state_manager import StateManager
from pixi.core.actions import ActionName
# Import your new perception modules
from pixi.perception.vision.face_detector import VisionProcessor
from pixi.perception.vision.gesture_detector import GestureProcessor

class LocalBrain:
    """
    The 'Fast Brain'. 
    1. Processes raw sensors (Vision/Gesture).
    2. Updates internal state (Hunger/Energy).
    3. Calculates Utility Scores.
    4. Returns the winning Action.
    """

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # Initialize Perception
        self.face_detector = VisionProcessor(min_face_confidence=0.6)
        self.gesture_detector = GestureProcessor(detection_interval_ms=200)
        
        # Track last known face for continuity
        self.last_face_data: Optional[Dict[str, float]] = None

    def decide(self, frame: np.ndarray, is_listening: bool = False, is_touching: bool = False) -> Dict[str, Any]:
        """
        Main Loop function.
        Args:
            frame: Raw opencv image.
            is_listening: True if hotword detected (Audio Override).
            is_touching: True if touch sensor active (Touch Override).
        Returns:
            {
                "action": ActionName,
                "reason": str,
                "face_data": dict (for motor control),
                "gesture": str
            }
        """
        # ---------------------------------------------------------
        # 1. PERCEPTION LAYER (See)
        # ---------------------------------------------------------
        # Run Face Detection
        vision_events = self.face_detector.process_frame(frame)
        
        # Extract primary face
        face_data = None
        for event in vision_events:
            if event.summary == "face_detected":
                # We found a face!
                face_data = event.data
                # Update State Manager so it knows we are socializing
                self.state.update_face_target(
                    face_id="user",
                    center_x=face_data.get("center_x", 0.5),
                    center_y=face_data.get("center_y", 0.5),
                    area=face_data.get("area", 0.0),
                    confidence=face_data.get("confidence", 0.0)
                )
                break # Only care about the first/biggest face
        
        self.last_face_data = face_data

        # Run Gesture Detection
        gesture = self.gesture_detector.process_frame(frame)

        # ---------------------------------------------------------
        # 2. STATE LAYER (Feel)
        # ---------------------------------------------------------
        # Tick the clock (decay energy, increase hunger)
        self.state.tick()
        current_state = self.state.get_state()

        # ---------------------------------------------------------
        # 3. UTILITY LAYER (Decide)
        # ---------------------------------------------------------
        
        scores = {}
        
        # --- PRIORITY 0: SURVIVAL (Low Battery) ---
        if current_state['energy'] < 0.15:
            print(f"[DEBUG] Low Battery Triggered! Energy: {current_state['energy']:.2f}") # TODO: Remove after debug
            return self._pack_decision(ActionName.GO_TO_SLEEP, "Low Battery Critical", face_data, gesture)

        # --- PRIORITY 1: LISTENING OVERRIDE ---
        if is_listening:
            # If we are listening, we MUST be quiet and still.
            return self._pack_decision(ActionName.IGNORE, "Listening to User", face_data, gesture)

        # --- PRIORITY 2: GESTURE COMMANDS ---
        # Explicit human commands override robot desires.
        if gesture == "Open_Palm" or gesture == "Stop":
            return self._pack_decision(ActionName.AVOID_OBSTACLE, "User signalled STOP", face_data, gesture)
        
        if gesture == "Thumb_Up":
            return self._pack_decision(ActionName.DO_A_HAPPY_DANCE, "User liked me!", face_data, gesture)

        # --- PRIORITY 3: TOUCH ---
        if is_touching:
             # Note: You need to add ENJOY_TOUCH to your actions.py if not there, 
             # otherwise map to WIGGLE_EXCITEDLY for now.
            return self._pack_decision(ActionName.WIGGLE_EXCITEDLY, "Being petted", face_data, gesture)

        # --- PRIORITY 3.5: PERSONAL SPACE ---
        # If face is too big (too close), back away.
        if face_data and face_data.get("area", 0.0) > 0.28:
            return self._pack_decision(ActionName.BACK_AWAY_SCARED, "Personal Space Violation", face_data, gesture)

        # --- PRIORITY 4: UTILITY SCORING ---
        
        # A. Social / Follow
        # We follow if we see a face AND we aren't too tired.
        if face_data:
            # Score increases if we are lonely (attention_hunger)
            follow_score = (current_state['attention_hunger'] * 2.0) + 0.5
            scores[ActionName.FOLLOW_PERSON] = follow_score
            
            # If we JUST saw the face (and haven't greeted recently), Greet.
            # (Simple logic: if confidence is high and we are 'curious')
            if current_state['curiosity'] > 0.6:
                scores[ActionName.GREET_HAPPILY] = 1.2 
        else:
            scores[ActionName.FOLLOW_PERSON] = 0.0
            scores[ActionName.GREET_HAPPILY] = 0.0

        # B. Search (Lonely but no face)
        if not face_data and current_state['attention_hunger'] > 0.7:
            scores[ActionName.SEARCH_FOR_HUMAN] = current_state['attention_hunger'] * 1.5
        else:
            scores[ActionName.SEARCH_FOR_HUMAN] = 0.0

        # C. Play / Dance
        # Needs high energy and excitement
        scores[ActionName.DO_A_HAPPY_DANCE] = (current_state['excitement'] * current_state['energy']) * 0.7

        # D. Sleep / Nap (Boredom)
        # If very bored or somewhat tired
        nap_score = (current_state['boredom'] * 1.0) + ((1.0 - current_state['energy']) * 0.5)
        # Map 'Nap' to GO_TO_SLEEP for now, or IGNORE/LOOK_AROUND
        scores[ActionName.LOOK_AROUND] = 0.2 # Base baseline
        
        if nap_score > 0.8:
             scores[ActionName.GO_TO_SLEEP] = nap_score

        # E. CURIOSITY (Head Tilt)
        # Logic: I see a face, I'm curious, but I don't need to move full body.
        # This fills the gap between "Sitting" and "Greeting".
        if face_data and current_state['curiosity'] > 0.5:
             # Higher score if we aren't moving much
             scores[ActionName.TILT_HEAD_CURIOUSLY] = current_state['curiosity'] * 1.2
        else:
             scores[ActionName.TILT_HEAD_CURIOUSLY] = 0.0

        # F. AFFECTION (Come Closer)
        # Logic: I am STARVING for attention. Normal 'Follow' is not enough.
        # This overrides 'Follow' when hunger is extreme.
        if face_data and current_state['attention_hunger'] > 0.85:
            scores[ActionName.COME_CLOSER] = current_state['attention_hunger'] * 3.0
        else:
            scores[ActionName.COME_CLOSER] = 0.0

        # G. BIOLOGICAL IDLE (Stretch)
        # Logic: I'm getting bored (0.4-0.7), but not tired enough to sleep yet.
        # This prevents the robot from freezing like a statue.
        if 0.4 < current_state['boredom'] < 0.8:
            scores[ActionName.STRETCH] = current_state['boredom'] * 0.8
        else:
            scores[ActionName.STRETCH] = 0.0

        # ---------------------------------------------------------
        # 4. SELECT WINNER
        # ---------------------------------------------------------
        best_action = max(scores, key=scores.get)
        best_score = scores[best_action]
        
        # Update state with the decision (so we don't repeat greetings)
        self.state.update_after_action(best_action)

        return self._pack_decision(
            best_action, 
            f"Utility Score: {best_score:.2f}", 
            face_data, 
            gesture
        )

    def _pack_decision(self, action, reason, face, gesture):
        return {
            "action": action,
            "reason": reason,
            "face_data": face, # Passed to motor driver to know WHERE to turn
            "gesture": gesture
        }