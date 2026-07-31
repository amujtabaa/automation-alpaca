# Borrowing plan and proprietary boundary

No surveyed project provides the complete desired system. The low-complexity strategy is to
borrow tested contracts and development techniques, not combine several runtimes into a fragile
stack.

## Adoption decisions

| Resource | Decision | Borrow | Do not borrow | When |
|---|---|---|---|---|
| Hypothesis | Direct dependency already available in the repo | Rule-based state-machine generation, shrinking, permanent regression examples | — | Foundation |
| NautilusTrader | Pattern/source reference; optional isolated spike | Order FSM, emulation triggers, own-order ownership, reconciliation reports, adapter conformance matrix | Whole platform migration, evolving event-sourcing subsystem, standard trailing policy | Foundation and adapter work |
| QuantConnect LEAN | Behavioral reference and separate feasibility spike | Broker capability models, order properties, adapter/integration tests, Webull feasibility evidence | Embedding its C# runtime, assuming its strategy persistence solves protection recovery | Broker roadmap |
| Barter-rs | Pattern only | One authoritative hot state, monotonic sequence, disabled-trading semantics, read-only replicas | Crypto connectors/runtime | Architecture |
| Exchange Core | Kernel principles only | Fixed-point values, sequenced mutation lane, snapshots/journal benchmarks | Java matching engine or Disruptor deployment | Foundation |
| Lumibot | Comparative test case | Smart-limit spread walk as a baseline scenario | Runtime dependency, market-order fallback, copied code under unclear README/license conflict | Executor validation |
| Vibe-Trading | Future trust-boundary reference | Mandates, deterministic IDs, credential separation, AI outside execution authority | Runtime AI control of the broker | Only if Signal Seat is redesigned later |
| CppTrader | Defer | Book-processing/profiling ideas if local book processing is measured as the bottleneck | C++ dependency now | Performance phase only |
| `cedwies/low-latency-trading` | Do not integrate | Microbenchmark inspiration at most | Queue/pool/simulator code; no clear standard license, broker, recovery, or protection | Possibly never |

## NautilusTrader: closest mechanics

Useful primary references:

- [Emulated orders](https://nautilustrader.io/docs/latest/concepts/orders/emulated/) show local
  quote/trade-triggered order emulation that releases fundamental market/limit orders and restores
  held emulated orders from a configured cache after restart.
- [Execution adapter testing specification](https://nautilustrader.io/docs/latest/developer_guide/spec_exec_testing/)
  provides capability-scoped order, fill, modify, cancel, rejection, and reconciliation tests.
- [Adapter development guide](https://nautilustrader.io/docs/latest/developer_guide/adapters/)
  separates instruments, market data, execution, reports, configuration, and factories.
- [Live trading/reconciliation concepts](https://nautilustrader.io/docs/latest/concepts/live/)
  are a strong source for unknown outcomes and startup broker reports.

Adapt the contracts and test cards into small Python interfaces. Do not maintain a broad Nautilus
fork. A later spike may run the same scenario corpus against a pinned Nautilus release, but the
reset does not depend on that spike succeeding.

Nautilus is LGPL-3.0-or-later. If it later becomes a linked dependency or distributed component,
perform a license review and keep proprietary policy modules cleanly separated.

## LEAN and Webull

LEAN currently documents live brokerage integrations for Webull, Alpaca, Interactive Brokers, and
Tradier. Its [Webull brokerage documentation](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/webull)
describes equity market/limit/stop/stop-limit/trailing orders, outside-RTH support for eligible
non-market equity orders, order updates, and request limits. It also says its Webull integration
does not supply a Webull live-data feed and uses another provider.

This makes Webull feasibility materially better than an estimate based on reverse engineering,
but it does not produce a reusable public Python adapter for this repo. Keep the Automation Alpaca
reset broker-specific to Alpaca. Run a separate, bounded LEAN/Webull spike only after the protection
kernel passes its Alpaca Paper milestones.

LEAN’s Apache-2.0 broker repositories and `IBrokerage` patterns are useful references. Its live
deployment state/reconciliation model is not automatically strong enough for an unattended
protection supervisor.

## Barter-rs and Exchange Core

[Barter-rs](https://github.com/barter-rs/barter-rs) demonstrates the topology needed here: one
cache-friendly authoritative engine state and downstream audit/state replicas. Its connectors are
crypto-oriented, so only the ownership pattern transfers.

[Exchange Core](https://github.com/exchange-core/exchange-core) is a matching engine, not a retail
broker client. Borrow fixed-point arithmetic, deterministic command sequencing, snapshot/journal
concepts, and latency measurement. Adding its runtime would increase operational complexity
without solving broker ambiguity.

## Stateful testing

[Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) is the
highest-value immediate adoption. The reference model generates and shrinks:

- partial, duplicate, delayed, and out-of-order fills;
- submit/cancel/replace acknowledgement and timeout;
- process crash at every durable-write/network boundary;
- stale, crossed, missing, and dislocated market data;
- trail activation, normal exit, hard bail, and session handoff;
- reconnect, targeted reconciliation, manual flatten, and kill switch.

Every shrunk P0/P1 history is checked in as a named regression fixture. This replaces large
numbers of speculative example tests with a smaller executable state model plus targeted broker
cases.

## What may be contributed upstream or open-sourced

Contribute only generic, independently useful work:

- verified bug fixes to an upstream dependency;
- broker capability documentation and conformance tests;
- generic normalized order/fill/report types;
- deterministic broker-simulator primitives;
- Hypothesis strategies for order lifecycle testing;
- adapter rate-limit/reconnect utilities that contain no policy advantage;
- documentation corrections backed by a public reproduction.

Do not open-source a large unstable framework merely to obtain review. Upstream contributions
should be small, licensed, and already proved locally.

## Keep proprietary

- `PositionProtectionSupervisor` transition policy;
- hard-bail evidence and escalation rules;
- hybrid trail composition, activation, and tightening;
- liquidity scoring, child sizing, price stages, hysteresis, and urgency;
- normal-exit to hard-bail escalation;
- session/native handoff policy;
- data-confidence thresholds and degraded-state precedence;
- configuration values, calibration results, promotion thresholds, and live incident corpus.

The generic interfaces can be visible without disclosing the strategy encoded behind them.

## Explicit non-adoptions

- No Nautilus, LEAN, Exchange Core, CppTrader, or Barter runtime in the first reset milestone.
- No multi-language process boundary.
- No lock-free queue or memory pool before profiling.
- No “smart limit” package that falls back to a market order.
- No copied code from a repository whose license is unclear or inconsistent.
