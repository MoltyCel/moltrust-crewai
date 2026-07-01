"""Exceptions for moltrust-crewai."""


class MolTrustCrewAIError(Exception):
    """Base error for the moltrust-crewai middleware."""


class AgentNotRegistered(MolTrustCrewAIError):
    """The DID has no MolTrust registration / reputation record.

    Raised by the client when the registry returns 404 for a DID. The
    guardrail treats an unregistered agent as failing the trust check
    (there is no verifiable history to trust).
    """

    def __init__(self, did: str):
        self.did = did
        super().__init__(f"Agent not registered with MolTrust: {did}")


class TrustCheckFailed(MolTrustCrewAIError):
    """An agent's trust score is below the configured minimum.

    Only raised when the guardrail is configured with ``action="raise"``.
    In the default ``action="block"`` mode the guardrail returns ``False``
    to CrewAI (blocking the tool call) instead of raising.
    """

    def __init__(self, did: str, score: float, min_score: float):
        self.did = did
        self.score = score
        self.min_score = min_score
        super().__init__(
            f"Trust check failed for {did}: score {score} < min_score {min_score}"
        )
