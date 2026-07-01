"""Direct HTTP client for the MolTrust trust-score API.

The guardrail depends only on ``get_trust_score(did) -> Optional[float]``, which
reads the agent's **0-100 behavioral trust score** from
``GET /skill/trust-score/{did}``. Scores are recomputable — the on-chain
solvency component is independently verifiable at ``/credits/solvency/{did}``.

No SDK wrapper: a direct ``requests`` call. **Tier 1 (keyless)** works with no
API key (rate-limited); **Tier 2** sends an ``X-API-Key`` header when an
``api_key`` / ``MOLTRUST_API_KEY`` is provided (higher rate limits).
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from .exceptions import AgentNotRegistered, MolTrustCrewAIError
from . import __version__

DEFAULT_BASE_URL = "https://api.moltrust.ch"


class TrustClient:
    """Fetch a DID's MolTrust trust score (0-100) via ``/skill/trust-score/{did}``.

    Args:
        api_key: Optional MolTrust API key (Tier 2). Falls back to the
            ``MOLTRUST_API_KEY`` env var. If neither is set, runs keyless (Tier 1).
        base_url: API base URL (default ``https://api.moltrust.ch``).
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
    ):
        # Optional by design: None => keyless Tier-1 mode.
        self._api_key = api_key or os.environ.get("MOLTRUST_API_KEY")
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout

    def get_trust_score(self, did: str) -> Optional[float]:
        """Return the agent's 0-100 trust score, or ``None`` if withheld/unscored.

        Reads ``GET /skill/trust-score/{did}`` and returns the ``trust_score``
        field. Returns ``None`` when the response has ``withheld == true`` or
        ``trust_score == null`` (a registered agent with no score yet) — the
        caller decides fail-open vs fail-closed.

        Raises:
            AgentNotRegistered: the DID is unknown to the registry (HTTP 404).
            MolTrustCrewAIError: on any other HTTP / transport error.
        """
        url = f"{self._base_url}/skill/trust-score/{did}"
        headers = {"User-Agent": f"moltrust-crewai/{__version__}"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        try:
            resp = requests.get(url, headers=headers, timeout=self._timeout)
        except requests.RequestException as exc:
            raise MolTrustCrewAIError(f"MolTrust request failed for {did}: {exc}") from exc

        if resp.status_code == 404:
            raise AgentNotRegistered(did)
        if resp.status_code >= 400:
            raise MolTrustCrewAIError(f"MolTrust returned HTTP {resp.status_code} for {did}")

        try:
            data = resp.json()
        except ValueError as exc:  # non-JSON body
            raise MolTrustCrewAIError(f"MolTrust returned non-JSON for {did}") from exc

        if data.get("withheld") or data.get("trust_score") is None:
            return None  # registered, but no score available yet
        return float(data["trust_score"])
