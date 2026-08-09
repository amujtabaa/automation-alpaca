# M1.5 option matrix

Status: **TASK A CANDIDATE — NOT ACCEPTED AUTHORITY**

| Option | Beta safety | M2 portability | Complexity | Disposition |
|---|---|---|---|---|
| A. Permanent Alpaca/Paper literals in every durable table | Keeps beta narrow | Forces schema recut for any later provider | Low now, high later | Rejected |
| B. General multi-broker runtime with routing/failover | Expands authority and failure modes | High | High | Rejected |
| C. One immutable provider-neutral connection profile per application generation | Keeps one authority and exact beta values | Supports reviewed new-generation recutover | Bounded | **Selected** |
| D. Mutable singleton broker settings | Allows identity drift after economic facts | Superficial | Medium and unsafe | Rejected |

Selected option C is portability without routing. Exactly one profile is mutation-eligible in an
application generation; during M2–M8 it must resolve to Alpaca Paper. A provider/account/origin/
credential/contract/capability change requires a new generation and reviewed recutover.

Market data is a separate decision axis. Binding a `MarketDataSourceProfile` commitment to a
`MarketStreamGenerationId` permits independent provenance without granting a feed implementation,
second execution authority, or premature M2 table.
