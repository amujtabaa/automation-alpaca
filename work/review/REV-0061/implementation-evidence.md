# Coverage-ratchet implementation evidence

The exact R1 candidate independently returned `ACCEPT`, P0=0/P1=0/P2=0,
at result SHA-256
`d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c`.

The subsequent fresh full repository run passed 5,977 tests and emitted JSON
SHA-256 `02941f1052a912a9484736f478e44495fc3ed08d4a4f719d90ba7eb168c638e0`:

- 24,826 / 26,530 executable lines = `93.577083%`;
- 8,462 / 9,920 branches = `85.302419%`.

The validator passed both dimensions. Ruff, Mypy, import contracts, R2 oracle,
and AI-OS governance gates also passed. No coverage exclusion, pragma,
instrumentation, source-selection, or application production change was used.

External exact-head Python 3.11/3.12 CI remains pending and is not claimed here.
