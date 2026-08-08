# WO-0151 R12-R1 activation disposition

Status: **PENDING RECORDS-ONLY ACTIVATION-DELTA REVIEW**

The exact R12-R1 semantic candidate independently ACCEPTed at P0=0/P1=0/P2=0:

- contract: 9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25;
- semantic manifest: this candidate manifest, pending its final hash; and
- result: 5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b.

The semantic acceptance is intentionally not source/test authorization. This
disposition freezes the next, narrower action: review only the named current
work-order, PKL, ledger, and provenance records that change their posture from
R12-R1 semantic ACCEPT to activation pending. The activation delta may not
modify the R12-R1 contract, semantic manifest, independent result, source,
tests, frozen E3 detector/evidence, or any ADR body.

If and only if the activation delta independently ACCEPTs at P0=0/P1=0:

1. stage exactly the named documentation/evidence paths, excluding the
   unaccepted R12 source/test working paths and frozen E3 detector;
2. run static diff/scope/ledger/PKL/disposition checks;
3. create one documentation-only activation commit;
4. record that exact commit SHA in a separately constrained reconciliation
   commit; and
5. only then authorize R12-R1 implementation in fills.py, acquisition.py,
   test_fill_position.py, and test_acquisition.py.

The normal branch push is authorized only for these documentation commits. A
subsequent live remote query is useful if credentials permit it, but no local
cache result may be presented as live remote evidence. WO-0152 remains paused
until R12-R1 implementation independently accepts and its unchanged detector
is rerun. The paired E2/E3 93% exact-head closeout and every existing safety
exclusion remain controlling.
