"""Mock-based tests for MolTrustGuardrail. No real API calls, no CrewAI needed.

The guardrail imports ``crewai.hooks`` only inside ``install()``, so the hook
logic (``before_tool_call``) is unit-testable in isolation with a fake context
and a fake trust client.
"""

import pytest

from moltrust_crewai import (
    MolTrustGuardrail,
    TrustCheckFailed,
)
from moltrust_crewai.exceptions import AgentNotRegistered, MolTrustCrewAIError


class FakeContext:
    """Stand-in for crewai.hooks.ToolCallHookContext."""

    def __init__(self, tool_name="search", tool_input=None, agent=None):
        self.tool_name = tool_name
        self.tool_input = tool_input if tool_input is not None else {}
        self.agent = agent


class FakeAgent:
    def __init__(self, role):
        self.role = role


class FakeClient:
    """Stand-in for TrustClient; returns a preset score or raises."""

    def __init__(self, score=None, raises=None):
        self._score = score
        self._raises = raises
        self.calls = []

    def get_trust_score(self, did):
        self.calls.append(did)
        if self._raises is not None:
            raise self._raises
        return self._score


DID = "did:moltrust:0123456789abcdef"


def _guard(score=None, raises=None, **kw):
    return MolTrustGuardrail(client=FakeClient(score=score, raises=raises), **kw)


# -- block mode ------------------------------------------------------------

def test_block_low_score_returns_false():
    g = _guard(score=42, min_score=60, action="block")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is False


def test_block_high_score_allows():
    g = _guard(score=88, min_score=60, action="block")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


def test_block_score_equal_min_allows():
    g = _guard(score=60, min_score=60, action="block")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


# -- no DID ----------------------------------------------------------------

def test_no_did_passes_by_default():
    g = _guard(score=0, min_score=60)
    assert g.before_tool_call(FakeContext(tool_input={})) is None


def test_no_did_blocked_when_pass_without_did_false():
    g = _guard(score=0, min_score=60, action="block", pass_without_did=False)
    assert g.before_tool_call(FakeContext(tool_input={})) is False


# -- warn / log modes ------------------------------------------------------

def test_warn_mode_allows_but_does_not_block():
    g = _guard(score=10, min_score=60, action="warn")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


def test_log_mode_allows():
    g = _guard(score=10, min_score=60, action="log")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


# -- raise mode ------------------------------------------------------------

def test_raise_mode_raises():
    g = _guard(score=5, min_score=60, action="raise")
    with pytest.raises(TrustCheckFailed) as ei:
        g.before_tool_call(FakeContext(tool_input={"did": DID}))
    assert ei.value.score == 5 and ei.value.min_score == 60


# -- registry / transport errors ------------------------------------------

def test_unregistered_agent_blocked_in_block_mode():
    g = _guard(raises=AgentNotRegistered(DID), min_score=60, action="block")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is False


def test_transport_error_fails_open():
    g = _guard(raises=MolTrustCrewAIError("boom"), min_score=60, action="block")
    # registry hiccup must not break the crew → allow (None)
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


# -- DID resolution --------------------------------------------------------

def test_resolve_did_from_agent_map():
    g = _guard(score=10, min_score=60, action="block",
               agent_did_map={"Researcher": DID})
    ctx = FakeContext(tool_input={}, agent=FakeAgent("Researcher"))
    assert g.before_tool_call(ctx) is False  # mapped DID → low score → block


def test_resolve_did_custom_key():
    g = _guard(score=10, min_score=60, action="block", did_key="agent_did")
    ctx = FakeContext(tool_input={"agent_did": DID})
    assert g.before_tool_call(ctx) is False


# -- config validation -----------------------------------------------------

def test_invalid_action_rejected():
    with pytest.raises(ValueError):
        MolTrustGuardrail(action="nope")


# -- withheld score (trust_score null / withheld=true) ---------------------

def test_withheld_score_blocked_in_block_mode():
    # get_trust_score returns None → treated as no verifiable score → block
    g = _guard(score=None, min_score=60, action="block")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is False


def test_withheld_score_allowed_in_warn_mode():
    g = _guard(score=None, min_score=60, action="warn")
    assert g.before_tool_call(FakeContext(tool_input={"did": DID})) is None


# -- TrustClient HTTP layer (mocked /skill/trust-score/{did}) --------------

from unittest import mock  # noqa: E402
import requests as _requests  # noqa: E402

from moltrust_crewai.client import TrustClient  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


def _client():
    return TrustClient(api_key="test-key")


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_returns_score_and_calls_skill_endpoint(mget):
    mget.return_value = FakeResponse(200, {"trust_score": 75, "withheld": False})
    assert _client().get_trust_score(DID) == 75.0
    args, kwargs = mget.call_args
    assert args[0].endswith(f"/skill/trust-score/{DID}")
    assert kwargs["headers"]["X-API-Key"] == "test-key"


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_withheld_returns_none(mget):
    mget.return_value = FakeResponse(200, {"trust_score": None, "withheld": True})
    assert _client().get_trust_score(DID) is None


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_null_score_returns_none(mget):
    mget.return_value = FakeResponse(200, {"trust_score": None, "withheld": False})
    assert _client().get_trust_score(DID) is None


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_404_raises_not_registered(mget):
    mget.return_value = FakeResponse(404, {})
    with pytest.raises(AgentNotRegistered):
        _client().get_trust_score(DID)


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_http_error_raises(mget):
    mget.return_value = FakeResponse(500, {})
    with pytest.raises(MolTrustCrewAIError):
        _client().get_trust_score(DID)


@mock.patch("moltrust_crewai.client.requests.get")
def test_client_network_error_raises(mget):
    mget.side_effect = _requests.RequestException("boom")
    with pytest.raises(MolTrustCrewAIError):
        _client().get_trust_score(DID)


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("MOLTRUST_API_KEY", raising=False)
    with pytest.raises(MolTrustCrewAIError):
        TrustClient()
