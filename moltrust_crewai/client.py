"""Thin wrapper over the official ``moltrust`` SDK.

Isolates the middleware from the SDK surface so the guardrail only depends on
a single ``get_trust_score(did) -> float`` call. The score is the agent's
MolTrust reputation score, which is **recomputable** — anyone can verify the
on-chain solvency component independently at
``https://api.moltrust.ch/credits/solvency/{did}``.
"""

from __future__ import annotations

import os
from typing import Optional

from .exceptions import AgentNotRegistered, MolTrustCrewAIError

DEFAULT_BASE_URL = "https://api.moltrust.ch"


class TrustClient:
    """Resolve a DID's MolTrust trust score via the ``moltrust`` SDK.

    Args:
        api_key: MolTrust API key. Falls back to the ``MOLTRUST_API_KEY``
            environment variable.
        base_url: API base URL (defaults to the SDK default / api.moltrust.ch).
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        try:
            from moltrust import MolTrust  # imported lazily so import errors are clear
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise MolTrustCrewAIError(
                "The 'moltrust' SDK is required. Install with: pip install 'moltrust>=0.2'"
            ) from exc

        key = api_key or os.getenv("MOLTRUST_API_KEY")
        if not key:
            raise MolTrustCrewAIError(
                "No MolTrust API key. Pass api_key=... or set MOLTRUST_API_KEY."
            )
        self._client = MolTrust(api_key=key, base_url=base_url or DEFAULT_BASE_URL)

    def get_trust_score(self, did: str) -> float:
        """Return the agent's MolTrust reputation score.

        Raises:
            AgentNotRegistered: if the DID is unknown to the registry (404).
            MolTrustCrewAIError: on any other SDK/transport error.
        """
        from moltrust import MolTrustError

        try:
            reputation = self._client.get_reputation(did)
        except MolTrustError as exc:
            if getattr(exc, "status_code", 0) == 404:
                raise AgentNotRegistered(did) from exc
            raise MolTrustCrewAIError(f"MolTrust lookup failed for {did}: {exc}") from exc
        return float(reputation.score)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
