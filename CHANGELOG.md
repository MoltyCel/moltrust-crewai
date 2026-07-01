# Changelog

All notable changes to `moltrust-crewai` are documented here. This project
follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-01

Initial release. Skeleton + working code (not yet published to PyPI).

### Added
- `MolTrustGuardrail` — trust verification via CrewAI 1.x hooks
  (`crewai.hooks.register_before_tool_call_hook` /
  `register_before_llm_call_hook`).
  - `before_tool_call` checks the calling agent's MolTrust trust score against
    `min_score`; returns `False` to block per the CrewAI hook contract.
  - `action` modes: `block` | `warn` | `log` | `raise`.
  - DID resolution via `agent_did_map` or `tool_input[did_key]`.
  - `install()` / `uninstall()` lifecycle + context-manager support.
  - Fails open on registry/transport errors; treats unregistered agents as
    failing the check.
- `TrustClient` — thin wrapper over the `moltrust` SDK (`get_reputation`).
- Exceptions: `MolTrustCrewAIError`, `AgentNotRegistered`, `TrustCheckFailed`.
- Mock-based test suite (no live API calls).
