from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Optional, Dict, Any

from pixi.core.actions import ActionName


class Mood(str, Enum):
    """High-level emotional states that influence Pixi's personality."""
    CURIOUS = "curious"
    HAPPY = "happy"
    PLAYFUL = "playful"
    ALERT = "alert"
    SLEEPY = "sleepy"
    SCARED = "scared"
    EXCITED = "excited"
    LONELY = "lonely"
    NEUTRAL = "neutral"


@dataclass(slots=True)
class InternalState:
    """Structured container for Pixi's internal signals."""
    mood: Mood = Mood.CURIOUS
    energy: float = 0.85  # 0.0 (Empty) - 1.0 (Full)
    curiosity: float = 0.65
    confidence: float = 0.55
    recognized_person: Optional[str] = None
    last_action: Optional[ActionName] = None
    attention_hunger: float = 0.35  # 0.0 (Satisfied) - 1.0 (Starving for love)
    excitement: float = 0.45
    caution: float = 0.3


class StateManager:
    """Tracks and updates Pixi's feelings, energy, and memories."""

    def __init__(
        self,
        *,
        boredom_timeout: float = 15.0,
        energy_decay_per_second: float = 0.003,
        curiosity_rise_per_second: float = 0.004,
        max_recent_actions: int = 8,
    ) -> None:
        self._state = InternalState()
        self._last_interaction_ts = time.time()
        self._last_tick_ts = self._last_interaction_ts
        self._boredom_timeout = boredom_timeout
        self._energy_decay = energy_decay_per_second
        self._curiosity_rise = curiosity_rise_per_second
        self._recent_actions: Deque[ActionName] = deque(maxlen=max_recent_actions)

    # ------------------------------------------------------------------
    # Timers & progression
    # ------------------------------------------------------------------
    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))

    def tick(self) -> None:
        """Updates energy/curiosity deltas based on elapsed real time."""
        now = time.time()
        delta = max(0.0, now - self._last_tick_ts)
        self._last_tick_ts = now

        # Energy decreases slowly over time
        new_energy = self._state.energy - (self._energy_decay * delta)
        self._state.energy = self._clamp(new_energy, 0.0, 1.0)

        # Boredom logic
        boredom_time = self.time_since_last_interaction() 
        
        # Curiosity rises when bored
        curiosity_delta = self._curiosity_rise * delta
        if boredom_time > self._boredom_timeout:
            curiosity_delta *= 1.8
        
        self._state.curiosity = self._clamp(self._state.curiosity + curiosity_delta, 0.1, 1.0)

        # Attention hunger grows if ignored
        attention_gain = 0.015 * delta
        if boredom_time > self._boredom_timeout:
            attention_gain *= 2.0
        self._state.attention_hunger = self._clamp(self._state.attention_hunger + attention_gain, 0.0, 1.0)

        # Excitement decays naturally
        excite_target = 0.2
        excite_delta = (excite_target - self._state.excitement) * 0.1 * delta
        self._state.excitement = self._clamp(self._state.excitement + excite_delta, 0.0, 1.0)

        # Caution decays (robot gets comfortable)
        caution_drop = 0.025 * delta
        self._state.caution = self._clamp(self._state.caution - caution_drop, 0.0, 1.0)

    def time_since_last_interaction(self) -> float:
        return time.time() - self._last_interaction_ts

    # ------------------------------------------------------------------
    # Event hooks
    # ------------------------------------------------------------------
    def register_interaction(self, person: Optional[str] = None) -> None:
        """Records that Pixi interacted with someone."""
        self._last_interaction_ts = time.time()
        # Interaction satisfies curiosity and hunger
        self._state.curiosity = self._clamp(self._state.curiosity - 0.1, 0.2, 1.0)
        self._state.confidence = self._clamp(self._state.confidence + 0.05, 0.0, 1.0)
        self._state.attention_hunger = self._clamp(self._state.attention_hunger - 0.25, 0.0, 1.0)
        self._state.excitement = self._clamp(self._state.excitement + 0.04, 0.1, 1.0)
        self._state.caution = self._clamp(self._state.caution - 0.05, 0.1, 1.0)
        if person:
            self._state.recognized_person = person

    def update_face_target(
        self,
        *,
        face_id: str,
        center_x: float,
        center_y: float,
        area: float,
        confidence: float,
    ) -> None:
        """Lightweight update when a face stays in view to aid tracking behaviour."""
        self._state.recognized_person = face_id
        self._last_interaction_ts = time.time()

        # Seeing a confident face lowers caution slightly and builds confidence over time.
        confidence_delta = 0.02 * self._clamp(confidence, 0.0, 1.0)
        self._state.confidence = self._clamp(self._state.confidence + confidence_delta, 0.0, 1.0)
        self._state.caution = self._clamp(self._state.caution - (confidence_delta * 0.6), 0.1, 1.0)

        # When someone is close-by (large area), satiate attention hunger a little.
        if area > 0.2:
            self._state.attention_hunger = self._clamp(self._state.attention_hunger - 0.01, 0.0, 1.0)

    def update_mood(self, new_mood: Mood) -> None:
        if self._state.mood != new_mood:
            # print(f"[State] Mood changed from {self._state.mood.value} to {new_mood.value}")
            self._state.mood = new_mood

    def update_after_action(self, action: ActionName) -> None:
        """Adjusts internal stats depending on the chosen action."""
        self._recent_actions.append(action)
        self._state.last_action = action

        # --- SURVIVAL ---
        if action == ActionName.EMERGENCY_SHUTDOWN:
            self._state.energy = 0.0
            self.update_mood(Mood.SLEEPY)

        # --- INTERACTION ---
        elif action == ActionName.ENJOY_TOUCH:
            self._state.attention_hunger = 0.0 # Fully satisfied
            self._state.caution = 0.0          # Fully trusts you
            self._state.excitement = self._clamp(self._state.excitement - 0.2, 0.0, 1.0) # Calms down
            self.update_mood(Mood.HAPPY)
            
        elif action == ActionName.GREET_HAPPILY:
            self._state.confidence += 0.1
            self._state.excitement += 0.15
            self.update_mood(Mood.HAPPY)

        elif action == ActionName.LISTEN_TO_USER:
            self._state.excitement = self._clamp(self._state.excitement - 0.1, 0.0, 1.0) # Focuses
            self.update_mood(Mood.ALERT)

        # --- SOCIAL ---
        elif action == ActionName.FOLLOW_PERSON:
            self._state.energy -= 0.04
            self._state.attention_hunger -= 0.1
            self.update_mood(Mood.CURIOUS)
            
        elif action == ActionName.SEARCH_FOR_HUMAN:
            self._state.energy -= 0.05 # Moving costs energy
            self._state.curiosity += 0.05
            self.update_mood(Mood.LONELY)
            
        elif action == ActionName.COME_CLOSER:
            self._state.attention_hunger -= 0.15
            self.update_mood(Mood.CURIOUS)

        # --- PLAY ---
        elif action == ActionName.DO_A_HAPPY_DANCE:
            self._state.energy -= 0.08
            self._state.excitement += 0.2
            self.update_mood(Mood.PLAYFUL)
            
        elif action == ActionName.WIGGLE_EXCITEDLY:
            self._state.energy -= 0.05
            self._state.excitement += 0.15
            self.update_mood(Mood.EXCITED)

        # --- IDLE / SAFETY ---
        elif action == ActionName.GO_TO_SLEEP:
            self._state.energy += 0.25 # Recharging
            self._state.excitement = 0.0
            self.update_mood(Mood.SLEEPY)
            
        elif action == ActionName.STRETCH:
            self._state.energy += 0.05
            self._state.curiosity += 0.05
            self.update_mood(Mood.NEUTRAL)
            
        elif action == ActionName.BACK_AWAY_SCARED:
            self._state.caution += 0.3
            self._state.confidence -= 0.2
            self.update_mood(Mood.SCARED)
            
        elif action == ActionName.AVOID_OBSTACLE:
            self._state.caution += 0.1
            self.update_mood(Mood.ALERT)

        # Clamp all values after update
        self._state.energy = self._clamp(self._state.energy)
        self._state.confidence = self._clamp(self._state.confidence)
        self._state.attention_hunger = self._clamp(self._state.attention_hunger)
        self._state.excitement = self._clamp(self._state.excitement)
        self._state.caution = self._clamp(self._state.caution)

        if action not in {ActionName.IGNORE, ActionName.BACK_AWAY_SCARED, ActionName.AVOID_OBSTACLE, ActionName.GO_TO_SLEEP}:
            self.register_interaction(self._state.recognized_person)

    # ------------------------------------------------------------------
    # State exposure
    # ------------------------------------------------------------------
    def get_state(self) -> dict:
        """Returns a serialisable snapshot for prompts or telemetry."""
        last_action_value = self._state.last_action.value if self._state.last_action else "NONE"
        
        # Calculate derived boredom score (0.0 - 1.0)
        # We consider the robot 'bored' if it hasn't interacted for a while.
        # Let's say max boredom is reached at 3 * timeout.
        time_since = self.time_since_last_interaction()
        boredom_score = self._clamp(time_since / (self._boredom_timeout * 3.0), 0.0, 1.0)

        return {
            "mood": self._state.mood.value,
            "energy": round(self._state.energy, 2),
            "curiosity": round(self._state.curiosity, 2),
            "confidence": round(self._state.confidence, 2),
            "attention_hunger": round(self._state.attention_hunger, 2),
            "excitement": round(self._state.excitement, 2),
            "caution": round(self._state.caution, 2),
            "boredom": round(boredom_score, 2),
            "time_since_last_interaction": round(time_since, 1),
            "recognized_person": self._state.recognized_person or "unknown",
            "last_action": last_action_value,
            "recent_actions": [action.value for action in self._recent_actions],
        }