# REV-0077 R7 author disposition

Date: 2026-08-23

Verdict: `ACCEPT-WITH-CHANGES`, accepted in full.

R8 will narrow scope correctly: runtime capability remains unissuable and is a hard WO-0168b
preflight hold; WO-0168c will not define or test nonexistent UOW outcomes/allowlists. R8 will also
narrow injected-exception propagation and remove the impossible copied-string claim. No wire, SQL,
DDL, binding, or checkpoint persistence design changes are required.

No source, test, DDL, SQLite, or serving action is authorized by this disposition.
