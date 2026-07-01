"""MolTrustGuardrail — trust verification for CrewAI tool/LLM calls.

Wires into CrewAI 1.x's global hook system (``crewai.hooks``). Before every
tool call, the calling agent's MolTrust trust score is checked against
``min_score``; agents below the threshold are blocked (or warned/logged,
depending on ``action``).

Usage::

    from moltrust_crewai import MolTrustGuardrail

    guard = MolTrustGuardrail(min_score=60).install()
    # ... run your Crew as usual; hooks fire automatically ...
    guard.uninstall()  # optional

CrewAI hook contract (verified against crewai.hooks.tool_hooks):
a ``before_tool_call`` hook receives a ``ToolCallHookContext`` and returns
``False`` to block execution, or ``True`` / ``None`` to allow it.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from .client import TrustClient
from .exceptions import AgentNotRegistered, MolTrustCrewAIError, TrustCheckFailed

logger = logging.getLogger("moltrust_crewai")

_VALID_ACTIONS = ("block", "warn", "log", "raise")


def _load_hook_registry() -> Dict[str, Callable[..., Any]]:
    """Import CrewAI's hook registration functions, with a clear error."""
    try:
        from crewai.hooks import (
            register_before_llm_call_hook,
            register_before_tool_call_hook,
            unregister_before_llm_call_hook,
            unregister_before_tool_call_hook,
        )
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise MolTrustCrewAIError(
            "This middleware needs CrewAI's hook system ('crewai.hooks'). "
            "Upgrade with: pip install 'crewai>=1.0'"
        ) from exc
    return {
        "register_tool": register_before_tool_call_hook,
        "register_llm": register_before_llm_call_hook,
        "unregister_tool": unregister_before_tool_call_hook,
        "unregister_llm": unregister_before_llm_call_hook,
    }


class MolTrustGuardrail:
    """Check calling agents against the MolTrust registry before tool/LLM calls.

    Args:
        min_score: Minimum acceptable MolTrust trust score. Agents scoring
            below this are subject to ``action``.
        action: ``"block"`` (return False → CrewAI skips the tool call),
            ``"warn"`` (log a warning, allow), ``"log"`` (log at info, allow),
            or ``"raise"`` (raise :class:`TrustCheckFailed`).
        api_key: MolTrust API key (else ``MOLTRUST_API_KEY`` env var).
        client: A preconstructed :class:`~moltrust_crewai.client.TrustClient`
            (mainly for testing / dependency injection).
        agent_did_map: Optional ``{agent_role_or_name: did}`` mapping used to
            resolve a CrewAI agent to its MolTrust DID.
        did_key: Key to look up a DID inside ``tool_input`` (default ``"did"``).
        pass_without_did: If True (default), calls with no resolvable DID are
            allowed through; if False, they are treated as failing the check.
    """

    def __init__(
        self,
        min_score: float = 60,
        action: str = "block",
        *,
        api_key: Optional[str] = None,
        client: Optional[TrustClient] = None,
        agent_did_map: Optional[Dict[str, str]] = None,
        did_key: str = "did",
        pass_without_did: bool = True,
    ):
        if action not in _VALID_ACTIONS:
            raise ValueError(f"action must be one of {_VALID_ACTIONS}, got {action!r}")
        self.min_score = min_score
        self.action = action
        self.agent_did_map = dict(agent_did_map or {})
        self.did_key = did_key
        self.pass_without_did = pass_without_did
        self._client = client  # lazily constructed on first use if None
        self._api_key = api_key
        self._registry: Optional[Dict[str, Callable[..., Any]]] = None
        self._installed = False

    # -- lifecycle ---------------------------------------------------------

    def install(self) -> "MolTrustGuardrail":
        """Register the before_tool_call / before_llm_call hooks globally."""
        if self._installed:
            return self
        self._registry = _load_hook_registry()
        self._registry["register_tool"](self.before_tool_call)
        self._registry["register_llm"](self.before_llm_call)
        self._installed = True
        logger.info("MolTrustGuardrail installed (min_score=%s, action=%s)",
                    self.min_score, self.action)
        return self

    def uninstall(self) -> None:
        """Unregister the hooks."""
        if not self._installed or not self._registry:
            return
        self._registry["unregister_tool"](self.before_tool_call)
        self._registry["unregister_llm"](self.before_llm_call)
        self._installed = False

    def __enter__(self) -> "MolTrustGuardrail":
        return self.install()

    def __exit__(self, *exc: Any) -> None:
        self.uninstall()

    # -- hooks -------------------------------------------------------------

    def before_tool_call(self, context: Any) -> Optional[bool]:
        """CrewAI before_tool_call hook. Return False to block, None to allow."""
        did = self._resolve_did(context)
        if not did:
            return None if self.pass_without_did else self._deny(None, None, context)

        try:
            score = self._get_client().get_trust_score(did)
        except AgentNotRegistered:
            logger.warning("MolTrust: agent %s is not registered", did)
            return self._deny(did, None, context)
        except MolTrustCrewAIError as exc:
            # Fail open on transport errors — do not break the crew on a
            # registry hiccup. Logged so it is never silent.
            logger.warning("MolTrust: trust lookup failed for %s (%s); allowing", did, exc)
            return None

        if score is None:
            # Registered but score withheld / not yet computed. No verifiable
            # score → same treatment as unregistered: fail-closed in "block",
            # fail-open in "warn"/"log" (per action).
            logger.warning("MolTrust: no trust score available for %s (withheld)", did)
            return self._deny(did, None, context)

        if score < self.min_score:
            return self._deny(did, score, context)

        logger.debug("MolTrust: %s passed (score=%s >= %s)", did, score, self.min_score)
        return None

    def before_llm_call(self, context: Any) -> None:
        """CrewAI before_llm_call hook.

        Placeholder for injecting trust context into the prompt. No-op by
        default so it is safe to register; override / extend as needed.
        """
        return None

    # -- internals ---------------------------------------------------------

    def _deny(self, did: Optional[str], score: Optional[float], context: Any) -> Optional[bool]:
        tool = getattr(context, "tool_name", "?")
        reason = "unregistered" if score is None else f"score {score} < {self.min_score}"
        if self.action == "block":
            logger.warning("MolTrust BLOCK tool=%s did=%s (%s)", tool, did, reason)
            return False
        if self.action == "warn":
            logger.warning("MolTrust WARN tool=%s did=%s (%s)", tool, did, reason)
            return None
        if self.action == "log":
            logger.info("MolTrust LOG tool=%s did=%s (%s)", tool, did, reason)
            return None
        # action == "raise"
        raise TrustCheckFailed(did or "<none>", score if score is not None else -1, self.min_score)

    def _get_client(self) -> TrustClient:
        if self._client is None:
            self._client = TrustClient(api_key=self._api_key)
        return self._client

    def _resolve_did(self, context: Any) -> Optional[str]:
        """Resolve the MolTrust DID for the agent behind this call.

        Order: (1) explicit agent_did_map by agent role/name,
        (2) a DID carried in tool_input under ``did_key``.
        """
        agent = getattr(context, "agent", None)
        if agent is not None and self.agent_did_map:
            key = getattr(agent, "role", None) or getattr(agent, "name", None)
            if key in self.agent_did_map:
                return self.agent_did_map[key]

        tool_input = getattr(context, "tool_input", None)
        if isinstance(tool_input, dict):
            did = tool_input.get(self.did_key)
            if isinstance(did, str) and did:
                return did
        return None
