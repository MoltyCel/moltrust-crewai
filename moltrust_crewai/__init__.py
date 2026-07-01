"""moltrust-crewai — trust verification middleware for CrewAI.

Add MolTrust trust checks to any CrewAI crew via CrewAI's hook system::

    from moltrust_crewai import MolTrustGuardrail

    MolTrustGuardrail(min_score=60).install()
"""

from .guardrail import MolTrustGuardrail
from .exceptions import (
    MolTrustCrewAIError,
    AgentNotRegistered,
    TrustCheckFailed,
)

__version__ = "0.1.0"
__all__ = [
    "MolTrustGuardrail",
    "MolTrustCrewAIError",
    "AgentNotRegistered",
    "TrustCheckFailed",
    "__version__",
]
