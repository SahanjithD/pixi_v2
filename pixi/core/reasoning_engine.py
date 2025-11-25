from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

try:  # Optional dependency for OpenRouter support
    from langchain_openai import ChatOpenAI
except (ImportError, ModuleNotFoundError):
    ChatOpenAI = None

from pixi.core.actions import ACTION_REGISTRY, ActionName
from pixi.core.state_manager import StateManager

PROMPT_TEMPLATE = (
    "You are Pixi's cognition module.\n"
    "Current internal state:\n{state_block}\n\n"
    "Recent events:\n{event_block}\n\n"
    "Action catalogue:\n{actions_block}\n\n"
    "Respond with valid JSON: {{\"action\": \"<ACTION_NAME>\", \"reason\": \"<brief rationale>\"}}."
)


class ReasoningEngine:
    def __init__(
        self,
        *,
        state_manager: Optional[StateManager] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.4,
    ) -> None:
        load_dotenv()

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        groq_api_key = os.getenv("GROQ_API_KEY")

        self._state_manager = state_manager or StateManager()
        self._actions = ACTION_REGISTRY

        if openrouter_api_key:
            if ChatOpenAI is None:
                raise RuntimeError("OpenRouter support requires `langchain-openai`.")
            model = model_name or os.getenv("OPENROUTER_MODEL_NAME") or "openai/gpt-4o-mini"
            self._llm = ChatOpenAI(
                api_key=openrouter_api_key,
                model=model,
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                temperature=temperature,
            )
        elif groq_api_key:
            model = model_name or os.getenv("GROQ_MODEL_NAME") or "llama-3.1-8b-instant"
            self._llm = ChatGroq(
                groq_api_key=groq_api_key,
                model_name=model,
                temperature=temperature,
            )
        else:
            raise RuntimeError("Missing OPENROUTER_API_KEY or GROQ_API_KEY.")
        
        self._chain = self._llm

    def decide_action(self, events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy method for event-based reasoning (optional use)."""
        self._state_manager.tick()
        state_snapshot = self._state_manager.get_state()

        payload = {
            "state_block": self._format_state(state_snapshot),
            "event_block": self._format_events(events),
            "actions_block": self._actions.to_prompt_list(),
        }

        prompt_text = PROMPT_TEMPLATE.format(**payload)
        result = self._chain.invoke(prompt_text)
        raw_text = str(result.content) if hasattr(result, "content") else str(result)

        action, reason = self._extract_action(raw_text)
        self._state_manager.update_after_action(action)

        return {"action": action, "reason": reason, "state": state_snapshot}

    def decide_action_from_text(self, user_text: str) -> ActionName:
        """
        Process spoken text and map it to a physical emotion/action.
        Pixi CANNOT speak, so it must respond with behavior.
        """
        # 1. Update State
        self._state_manager.tick()
        self._state_manager.register_interaction(person="voice_user")
        state_snapshot = self._state_manager.get_state()
        
        # 2. Non-Verbal Prompt
        prompt = (
            f"You are Pixi, a robot that CANNOT SPEAK. You communicate only through "
            f"sounds and body language. A user just said: \"{user_text}\"\n\n"
            f"Your current state: {json.dumps(state_snapshot)}\n"
            f"Available Actions: {self._actions.to_prompt_list()}\n\n"
            "INSTRUCTIONS:\n"
            "1. Choose ONE action that best conveys your emotional response.\n"
            "   - If 'Hello' -> GREET_HAPPILY.\n"
            "   - If 'Dance' -> DO_A_HAPPY_DANCE.\n"
            "   - If confusing question -> TILT_HEAD_CURIOUSLY.\n"
            "   - If mean -> BACK_AWAY_SCARED.\n"
            "2. Return ONLY a valid JSON object: {{\"action\": \"<ACTION_NAME>\"}}\n"
            "3. Do NOT include any spoken text."
        )

        # 3. Call LLM
        try:
            result = self._chain.invoke(prompt)
            raw_text = str(result.content) if hasattr(result, "content") else str(result)
            action, _ = self._extract_action(raw_text)
            
            # Fallback: If LLM gets confused and returns default/look_around for a direct query
            if action == ActionName.LOOK_AROUND:
                 return ActionName.TILT_HEAD_CURIOUSLY
                 
            return action
        except Exception as e:
            print(f"[ReasoningEngine] Error: {e}")
            return ActionName.TILT_HEAD_CURIOUSLY

    def _format_state(self, state: Dict[str, Any]) -> str:
        keys = ["mood", "energy", "attention_hunger", "excitement", "caution", "recognized_person"]
        return "\n".join(f"- {key}: {state.get(key, 'n/a')}" for key in keys)

    def _format_events(self, events: Iterable[Dict[str, Any]]) -> str:
        items = [f"- {e.get('summary', 'unknown')}" for e in events]
        return "\n".join(items) if items else "- none"

    def _extract_action(self, raw_text: str) -> tuple[ActionName, str]:
        try:
            # Clean up potential markdown code blocks
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            payload = json.loads(clean_text)
        except json.JSONDecodeError:
            payload = {}

        action_raw = str(payload.get("action", "")).strip().upper()
        reason = str(payload.get("reason", "")).strip() or "No reason provided."
        action = self._normalise_action(action_raw)
        return action, reason

    def _normalise_action(self, action_raw: str) -> ActionName:
        # Direct match
        if action_raw in ActionName.__members__:
            return ActionName[action_raw]
            
        # Synonym/Fuzzy match
        for candidate in ActionName:
            if candidate.value == action_raw:
                return candidate

        synonyms = {
            "HAPPY": ActionName.DO_A_HAPPY_DANCE,
            "DANCE": ActionName.DO_A_HAPPY_DANCE,
            "WIGGLE": ActionName.WIGGLE_EXCITEDLY,
            "GREET": ActionName.GREET_HAPPILY,
            "HELLO": ActionName.GREET_HAPPILY,
            "SCARED": ActionName.BACK_AWAY_SCARED,
            "STOP": ActionName.AVOID_OBSTACLE,
        }
        
        for key, mapped in synonyms.items():
            if key in action_raw:
                return mapped

        return ActionName.LOOK_AROUND