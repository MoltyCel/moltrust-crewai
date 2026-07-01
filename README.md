# moltrust-crewai

**Add trust verification to CrewAI in one line.**

`moltrust-crewai` checks the calling agent's **MolTrust trust score** before
every tool call in a [CrewAI](https://github.com/crewAIInc/crewAI) crew. Agents
below your minimum score are blocked (or warned/logged). It hooks into CrewAI's
native hook system — no changes to your agents or tasks.

## Install

```bash
pip install moltrust-crewai
```

## Usage (one line)

```python
from moltrust_crewai import MolTrustGuardrail

# register the guardrail globally, then run your crew as usual
MolTrustGuardrail(min_score=60).install()

from crewai import Crew
crew = Crew(agents=[...], tasks=[...])
crew.kickoff()
```

That's it — the guardrail fires automatically on every tool call via
`crewai.hooks`. Set `MOLTRUST_API_KEY` in your environment (or pass
`api_key=...`).

> **Note on the API:** CrewAI 1.x wires middleware through its **hook system**
> (`crewai.hooks`), not a `Crew(callbacks=[...])` argument. `install()`
> registers the `before_tool_call` / `before_llm_call` hooks for you. Call
> `guard.uninstall()` (or use it as a context manager) to remove them.

### Options

```python
MolTrustGuardrail(
    min_score=60,          # min trust score, 0-100 scale (see below)
    action="block",        # "block" | "warn" | "log" | "raise"
    agent_did_map={         # map a CrewAI agent role → its MolTrust DID
        "Researcher": "did:moltrust:0123456789abcdef",
    },
    did_key="did",         # or read the DID from tool_input["did"]
    pass_without_did=True,  # allow calls with no resolvable DID
)
```

## What it does

Before every tool call, `MolTrustGuardrail` resolves the calling agent's
MolTrust DID (via `agent_did_map` or a `did` in the tool input) and reads its
trust score from `GET /skill/trust-score/{did}`. `min_score` is on the
**MolTrust trust score scale (0–100, behavioral trust)** — **not** the 0–5
reputation/rating scale. The CrewAI hook contract is simple: the hook returns
`False` to block the tool call, or `None`/`True` to allow it.

Trust scores are **recomputable** — you never have to take MolTrust's word for a
number. Verify the on-chain solvency component of any agent independently:

```
https://api.moltrust.ch/credits/solvency/{did}
```

## Difference from Microsoft AGT

[Microsoft's Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
enforces **policies** — *what an agent may do* (scope, sandboxing, zero-trust
identity). MolTrust verifies **behavioral trust** — *is this agent trustworthy,
based on verifiable history*. They are **complementary, not competing**: use AGT
to bound authority, use MolTrust to decide who has earned it.

## Honest limitations (0.1.0)

- CrewAI agents have no MolTrust DID by default — you map them explicitly via
  `agent_did_map`, or carry a `did` in the tool input. There is no magic
  auto-binding yet.
- `min_score` is on the **0–100 MolTrust trust score** (`trust_score` from
  `/skill/trust-score/{did}`), the phase-2 behavioral score — not the 0–5
  reputation/rating average.
- A **withheld** score (registered agent with too few endorsements → API
  returns `trust_score: null, withheld: true`) is treated like an unregistered
  agent: fail-closed in `block`, fail-open in `warn`/`log`.
- On a registry/transport error the guardrail **fails open** (allows the call,
  logs a warning) so a MolTrust hiccup never breaks your crew.
- `before_llm_call` is a no-op placeholder (a hook point for injecting trust
  context into prompts); extend it as needed.

## License

MIT © CryptoKRI GmbH — see [LICENSE](LICENSE).
