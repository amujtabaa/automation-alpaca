---
type: Review Result
rev_id: REV-0008
reviewer_model: GPT-5 Codex
verdict: BLOCK
date: 2026-07-10
---

## Verdict

**BLOCK.** The documented ADR-005/INV-074 claim that the route boundary rejects *any* new direct route-to-backend edge is not true as enforced. Contract 5 is an opt-in, hand-enumerated list and permits a route to obtain `StateStore` through the deliberately unguarded `app.api.deps.get_store` seam. That route could mutate order, control, or event-log state without a facade import or a Contract-5 violation.

The architecture-foundation gate must **not** clear until this bypass is mechanically closed. This result reviews frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4`. The required Python 3.12 runtime is unavailable on this host (only 3.14 is installed); `importlinter`, `grimp`, and `mypy` are also unavailable, so no Python-3.12 gate/test claim is made below.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---|---|---|---|---|
| ARCH-001 | P1 | `.importlinter:137-162`; `app/api/deps.py:26-29` | Frozen-source repro: the Contract-5 parser printed `route_list_missing_from_contract=[]` and `contract_route_sources_missing_from_tree=[]`, proving current names happen to match. It then printed `candidate_is_source=False`, `app.api.deps_is_forbidden=False`, `allow_indirect_imports=True`, and `candidate_direct_forbidden_edge=False` for a prospective `app.api.routes_escape -> app.api.deps.get_store` route. `get_store` returns `request.app.state.store`. There is no current route using `get_store` (the targeted grep returned no lines). The exact linter confirmation could not run because `importlinter`/Python 3.12 are absent. | ADR-005 says routes must not directly mutate stores, and `.importlinter:15-16,169-170` claims any new direct route-to-backend edge fails. A new route is outside the manually listed source set; even if added to it, importing `get_store` is neither forbidden nor a direct forbidden edge, while it exposes the raw store. This is a green-but-bypassable facade boundary for human-gated operations. | Derive Contract-5 sources from all `app.api.routes_*` modules (or add an independently maintained test that fails on an unlisted route). Prevent route access to raw-store DI: split composition-only providers from route-importable facade providers and forbid routes from importing the former, then add a regression fixture/temporary-module test that demonstrates both the new-file and `get_store` bypasses fail. |
| ARCH-002 | P2 | `app/facade/commands.py:3-24`; `app/facade/queries.py:3-8`; `app/facade/protocols.py:9-14` | The module docstrings still state that only Phase-1 methods are real and every other method raises `NotYetImplementedError`; the same files now describe P6a-P6e methods as real, and the AST comparison found no missing protocol methods, no extra public implementation methods, and no keyword-name mismatches. | The stale top-level contract description tells a maintainer that currently routed command/query methods are unimplemented, obscuring the actual enforced facade surface and making architecture review/error diagnosis needlessly unreliable. | Update the three module docstrings to the current Phase-6 surface, or explicitly label them historical and point to the current contract. |

## Proposed Fixes Summary

- Make the API-route/facade boundary closed over both present and future route modules and block dependency-injection access to raw stores from routes.
- Correct the obsolete facade-protocol status documentation.

## Notes

### Decisive evidence

```text
python (frozen `.importlinter` parser) output:
route_list_missing_from_contract= []
contract_route_sources_missing_from_tree= []
candidate_is_source= False
app.api.deps_is_forbidden= False
allow_indirect_imports= True
candidate_direct_forbidden_edge= False
route_can_receive_store_via= app.api.deps.get_store

git show b600101:app/api/deps.py (lines 26-29):
def get_store(request: Request) -> StateStore:
    return request.app.state.store

python environment probe:
importlinter= None
mypy= None
grimp= None
py -0p:  -V:3.14 * C:\Python314\python.exe
```

### Clean/null probes

```text
Current Contract-5 source list vs every b600101 app/api/routes_*.py:
route_list_missing_from_contract= []
contract_route_sources_missing_from_tree= []

Current models-leaf contract coverage:
models_forbidden_omissions_on_current_tree= ['app.__init__']
models_forbidden_stale_entries= []
(The package initializer is not a higher layer; no current omission found.)

git grep -n -E '^from app\\.|^import app\\.' b600101 -- cockpit
(no output: no cockpit-to-app import)

git grep -n -E 'alpaca\\.markets|api\\.alpaca|paper-api\\.alpaca|stream\\.data\\.alpaca' b600101 -- app cockpit
b600101:app/broker/alpaca_paper.py:57:# Source: https://docs.alpaca.markets/reference/getallorders-1 (status field).
(no current raw Alpaca HTTP reach found.)

git grep -n -E '^from app\\.store|^import app\\.store' b600101 -- app/events/projectors.py app/events/__init__.py
(no output: no store -> projectors -> store import cycle found.)

AST protocol/implementation comparison:
commands: port_missing_in_impl=[]; impl_public_not_in_port=[]
queries: port_missing_in_impl=[]; impl_public_not_in_port=[]
```

The generic Python 3.14 runtime-Protocol probe returned `runtime_protocol_accepts_wrong_signature=True`; it confirms that `@runtime_checkable` checks attribute presence rather than signatures, but no production `isinstance` use was found and it is not a gating finding. No full pytest, `lint-imports`, grimp, or mypy run was possible under the required Python 3.12 pin.
