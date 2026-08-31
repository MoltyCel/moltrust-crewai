"""M7 — lookup errors deny by default; opt-out and cache are the release valves."""
import pytest

from moltrust_crewai.guardrail import MolTrustGuardrail
from moltrust_crewai.exceptions import AgentNotRegistered, MolTrustCrewAIError

DID = "did:moltrust:aaaabbbbccccdddd"


class _Client:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def get_trust_score(self, did):
        self.calls += 1
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


class _Ctx:
    """Minimal stand-in for a CrewAI tool-call context."""
    def __init__(self, did=DID):
        self.agent_did = did


def _guard(behaviour, **kw):
    g = MolTrustGuardrail(client=_Client(behaviour), **kw)
    g._resolve_did = lambda ctx: getattr(ctx, "agent_did", None)
    return g


def test_lookup_error_now_blocks(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    g = _guard(MolTrustCrewAIError("down"))
    assert g.before_tool_call(_Ctx()) is False


def test_opt_out_restores_the_old_behaviour(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    g = _guard(MolTrustCrewAIError("down"), fail_open=True)
    assert g.before_tool_call(_Ctx()) is None


def test_env_var_opts_out(monkeypatch):
    monkeypatch.setenv("MOLTRUST_FAIL_OPEN", "yes")
    g = _guard(MolTrustCrewAIError("down"))
    assert g.before_tool_call(_Ctx()) is None


def test_a_brief_outage_rides_on_the_cached_score(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    g = _guard(MolTrustCrewAIError("down"), cache_ttl=0, cache_stale_grace=300)
    g._cache.put(DID, 90.0)
    assert g.before_tool_call(_Ctx()) is None


def test_a_stale_low_score_still_blocks(monkeypatch):
    monkeypatch.delenv("MOLTRUST_FAIL_OPEN", raising=False)
    g = _guard(MolTrustCrewAIError("down"), min_score=60, cache_ttl=0, cache_stale_grace=300)
    g._cache.put(DID, 10.0)
    assert g.before_tool_call(_Ctx()) is False


def test_good_score_passes():
    g = _guard(90.0, min_score=60)
    assert g.before_tool_call(_Ctx()) is None
