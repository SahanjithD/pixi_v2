from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Iterable, Optional, Sequence, Any

# Define the handler signature: accepts optional face_data and gesture arguments
ActionHandler = Callable[..., None]


class ActionName(str, Enum):
    """All high-level actions Pixi can perform."""
    # --- Priority 0: Survival ---
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"
    
    # --- Priority 1: Reflexes/Safety ---
    AVOID_OBSTACLE = "AVOID_OBSTACLE"
    BACK_AWAY_SCARED = "BACK_AWAY_SCARED"
    
    # --- Priority 2: Overrides ---
    LISTEN_TO_USER = "LISTEN_TO_USER"
    IGNORE = "IGNORE"
    
    # --- Priority 3: Interaction ---
    ENJOY_TOUCH = "ENJOY_TOUCH"
    GREET_HAPPILY = "GREET_HAPPILY"
    
    # --- Priority 4: Social/Tracking ---
    FOLLOW_PERSON = "FOLLOW_PERSON"
    COME_CLOSER = "COME_CLOSER"
    SEARCH_FOR_HUMAN = "SEARCH_FOR_HUMAN"
    
    # --- Priority 5: Play ---
    DO_A_HAPPY_DANCE = "DO_A_HAPPY_DANCE"
    WIGGLE_EXCITEDLY = "WIGGLE_EXCITEDLY"
    
    # --- Priority 6: Idle/Biological ---
    TILT_HEAD_CURIOUSLY = "TILT_HEAD_CURIOUSLY"
    STRETCH = "STRETCH"
    LOOK_AROUND = "LOOK_AROUND"
    GO_TO_SLEEP = "GO_TO_SLEEP"


@dataclass(slots=True)
class ActionDescriptor:
    name: ActionName
    description: str
    intent: str
    energy_cost: float = 0.0
    priority: int = 50
    tags: Sequence[str] = ()
    handler: Optional[ActionHandler] = None

    def dispatch(self, face_data: Optional[Dict[str, float]] = None, gesture: Optional[str] = None) -> None:
        """Executes the attached handler, passing context data if needed."""
        if self.handler is None:
            # Default fallback if no driver attached yet
            print(f"[ActionRegistry] '{self.name.value}' dispatched (No handler wired).")
            return
        
        # Pass data to the handler (e.g., for motors to know where to turn)
        try:
            self.handler(face_data=face_data, gesture=gesture)
        except TypeError:
            # Fallback for handlers that don't accept arguments
            self.handler()


class ActionRegistry:
    def __init__(self) -> None:
        self._registry: Dict[ActionName, ActionDescriptor] = {}

    def register(self, descriptor: ActionDescriptor) -> None:
        self._registry[descriptor.name] = descriptor

    def get(self, name: ActionName) -> Optional[ActionDescriptor]:
        return self._registry.get(name)

    def all(self) -> Iterable[ActionDescriptor]:
        return self._registry.values()

    def attach_handler(self, name: ActionName, handler: ActionHandler) -> None:
        if name in self._registry:
            self._registry[name].handler = handler
        else:
            print(f"[ActionRegistry] Warning: Cannot attach handler to unknown action '{name}'")


ACTION_REGISTRY = ActionRegistry()


def _register_default_actions() -> None:
    # --- PRIORITY 0: SURVIVAL ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.EMERGENCY_SHUTDOWN,
        description="Stop all motors and dim screen immediately.",
        intent="Protect battery life when critical.",
        priority=100,
        tags=("survival", "power")
    ))

    # --- PRIORITY 1: SAFETY ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.AVOID_OBSTACLE,
        description="Stop, step aside, or reroute around an obstacle.",
        intent="Prevent collisions and maintain safety.",
        energy_cost=0.03,
        priority=95,
        tags=("safety", "movement")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.BACK_AWAY_SCARED,
        description="Shuffle back slightly while showing a cautious expression.",
        intent="Create distance from surprising or uncomfortable stimuli.",
        energy_cost=0.03,
        priority=92,
        tags=("safety", "caution")
    ))

    # --- PRIORITY 2: OVERRIDES ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.LISTEN_TO_USER,
        description="Freeze motors and display listening face.",
        intent="Prioritize audio input over movement noise.",
        priority=95,
        tags=("interaction", "audio")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.IGNORE,
        description="Politely acknowledge but take no action.",
        intent="Use when busy or prioritizing other inputs.",
        energy_cost=0.0,
        priority=10,
        tags=("fallback",)
    ))

    # --- PRIORITY 3: INTERACTION ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.ENJOY_TOUCH,
        description="Stop moving, close eyes, and purr.",
        intent="React to physical affection.",
        priority=90,
        tags=("social", "touch")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.GREET_HAPPILY,
        description="Display a joyful face, wave, and chirp a cheerful greeting.",
        intent="Use when meeting or recognizing someone friendly.",
        energy_cost=0.05,
        priority=80,
        tags=("social", "positive")
    ))

    # --- PRIORITY 4: SOCIAL TRACKING ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.FOLLOW_PERSON,
        description="Move to keep the recognized person comfortably within view.",
        intent="Track and accompany a friendly human nearby.",
        energy_cost=0.06,
        priority=85,
        tags=("social", "movement")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.COME_CLOSER,
        description="Approach the person slowly and look up affectionately.",
        intent="Close distance to a trusted person when needy.",
        energy_cost=0.05,
        priority=78,
        tags=("social", "affection")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.SEARCH_FOR_HUMAN,
        description="Spin and patrol to find a face.",
        intent="Active search to satisfy attention hunger.",
        energy_cost=0.04,
        priority=60,
        tags=("social", "search")
    ))

    # --- PRIORITY 5: PLAY ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.DO_A_HAPPY_DANCE,
        description="Perform a short dance with lights and music to celebrate.",
        intent="Celebrate exciting moments or positive interactions.",
        energy_cost=0.08,
        priority=70,
        tags=("celebratory", "high-energy")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.WIGGLE_EXCITEDLY,
        description="Bounce in place with sparkling LEDs to share excitement.",
        intent="Express high excitement to nearby humans playfully.",
        energy_cost=0.07,
        priority=75,
        tags=("celebratory", "social")
    ))

    # --- PRIORITY 6: IDLE / BIOLOGICAL ---
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.TILT_HEAD_CURIOUSLY,
        description="Tilt head with blinking eyes to show curiosity.",
        intent="Use when unsure about a stimulus.",
        energy_cost=0.01,
        priority=40,
        tags=("idle", "curious")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.STRETCH,
        description="Extend body and shake to relieve stiffness.",
        intent="Idle behavior to look alive.",
        energy_cost=0.02,
        priority=20,
        tags=("idle", "biological")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.LOOK_AROUND,
        description="Pan the head slowly to survey the surroundings.",
        intent="Gather more context when nothing urgent is happening.",
        energy_cost=0.02,
        priority=35,
        tags=("scan", "idle")
    ))
    ACTION_REGISTRY.register(ActionDescriptor(
        name=ActionName.GO_TO_SLEEP,
        description="Dim lights, play a soft tune, and enter low-power pose.",
        intent="Recover energy when tired or inactive for long periods.",
        energy_cost=-0.2,
        priority=60,
        tags=("rest", "low-energy")
    ))


_register_default_actions()


def attach_stub_handlers(state_manager: Any = None) -> None:
    """Attach placeholder handlers until real hardware integrations are supplied."""
    def _stub(action_name: ActionName) -> ActionHandler:
        def _handler(face_data: Optional[Dict] = None, gesture: Optional[str] = None) -> None:
            # Simulating hardware action
            info = ""
            if face_data:
                info += f" [Target: x={face_data.get('center_x',0):.2f}]"
            if gesture:
                info += f" [Gesture: {gesture}]"
            
            state_debug = ""
            if state_manager:
                state_debug = f" [State: {state_manager.get_state()}]"

            print(f"[Hardware] Executing: {action_name.value}{info}{state_debug}\n") # TODO: Remove after debug
        return _handler

    for descriptor in ACTION_REGISTRY.all():
        if descriptor.handler is None:
            ACTION_REGISTRY.attach_handler(descriptor.name, _stub(descriptor.name))