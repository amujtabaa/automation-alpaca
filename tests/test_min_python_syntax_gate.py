"""Every EMBEDDED source string in `tests/` must be legal on the minimum Python.

**The defect this exists for.** `ruff target-version = "py311"` (D-7(a)) refuses
3.12-only syntax in repo source files. It cannot see 3.12-only syntax inside a
*string literal* that a test hands to `ast.parse` — and that is exactly the shape
that took CI red for **seven consecutive commits** on 2026-07-29, three of them
under an explicit "gates green" claim:

    async def f(s, e):
        return await getattr(s, f"append_{"execution_event"}")(e)

That is an adversarial fixture for the append-caller gate, stored as a string. The
file containing it parses fine on 3.11; the *fixture* does not, and it only fails
when `ast.parse` reaches it at test time — so the 3.11 CI leg caught it and every
local 3.12 run did not.

**Why a lint gate rather than a second interpreter.** The obvious fix is to parse
fixtures under 3.11. Two dead ends, both measured before landing this:

* `ast.parse(src, feature_version=(3, 11))` does **not** reject PEP 701 — verified
  on 3.12, it parses the 3.12-only form regardless. `feature_version` is
  best-effort and does not gate this syntax.
* Shelling to a real `python3.11` works but only where 3.11 is installed, which
  makes the gate a `skip` on the 3.12 leg — and a control that skips is the
  "inert evidence" class this repo keeps finding.

`ruff --target-version py311` is interpreter-independent: it is a config setting,
not a property of the running Python, so this gate has identical force on both
matrix legs and locally.

**No heuristic, deliberately.** An earlier attempt filtered to "strings that look
like code" (containing `def `, `return `, …) and was useless: it flagged 71
docstrings and found nothing real. This one collects *every* string literal that
parses as Python and lints all of them. Prose docstrings that happen to parse are
harmless — they produce no syntax error at py311 — so the noise costs nothing and
the filter that could hide a real fixture is gone. Measured: ~11.7k candidates,
one batched `ruff` invocation, **under 0.3 s**.

The gate is only as strong as ruff's version: version-aware syntax diagnostics are
verified on the `constraints.txt` pin (`ruff==0.15.20`). `requirements.txt` allows
`ruff>=0.6`, which does not guarantee them — so this suite also asserts that ruff
still reports the planted defect, rather than trusting that it does.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TESTS_DIR = _REPO_ROOT / "tests"

# The floor the repo supports (CLAUDE.md, D-7(a)). Kept as one literal because a
# second spelling of a version floor is how the contract drifted in the first place.
MIN_PYTHON_TARGET = "py311"

# The exact construct that broke the 3.11 leg, kept as the gate's own tripwire.
#
# ASSEMBLED AT RUNTIME, NOT STORED AS A LITERAL — and the first version of this
# module got that wrong. Written as a plain string constant, the collector below
# found it (correctly: it IS a string literal in tests/ that parses on 3.12 and
# not on 3.11) and the gate failed on itself. The tempting fix is an allowlist
# exempting this file, but an exemption mechanism is exactly how the append-caller
# gate was defeated five times. So instead there is no illegal literal here at
# all: `Q` is substituted for the quote character after the fact, so every string
# literal in this file is legal on 3.11 and the gate needs no exceptions to pass.
_PLANTED_312_ONLY_SOURCE = (
    "async def f(s, e):\n    return await getattr(s, fQappend_{Qexecution_eventQ}Q)(e)\n"
).replace("Q", '"')


def _embedded_python_sources() -> list[tuple[str, int, str]]:
    """Every string literal under `tests/` that parses as Python on this runtime.

    Parsing on the *current* interpreter is the right filter: a string that is not
    Python here is prose or a partial snippet, and cannot be a fixture that
    `ast.parse` consumes successfully. Anything that does parse is a candidate,
    whatever it looks like.
    """

    found: list[tuple[str, int, str]] = []
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - ruff fails the build first
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            try:
                ast.parse(node.value)
            except (SyntaxError, ValueError, UnicodeEncodeError):
                # Prose, a partial snippet, or a lone-surrogate adversarial
                # fixture — not valid Python on this interpreter either.
                continue
            found.append((path.name, node.lineno, node.value))
    return found


def _ruff_syntax_findings(sources: list[tuple[str, int, str]], workdir: Path) -> str:
    """Lint every candidate at the minimum target in ONE ruff invocation.

    `--isolated` so the repo's own ruff config (excludes, rule selection) cannot
    affect the result; `--select=F401` narrows the semantic rules to something
    inert, because syntax errors are reported regardless of selection and are the
    only thing this gate reads.
    """

    index: dict[str, tuple[str, int, str]] = {}
    for i, (name, lineno, src) in enumerate(sources):
        stem = f"f{i:05d}.py"
        (workdir / stem).write_text(src, encoding="utf-8", errors="surrogatepass")
        index[stem] = (name, lineno, src)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--target-version",
            MIN_PYTHON_TARGET,
            "--select=F401",
            str(workdir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr

    offenders: list[str] = []
    for line in output.splitlines():
        if "invalid-syntax" not in line:
            continue
        offenders.append(line.strip())
    if not offenders:
        return ""

    # Map ruff's temp filenames back to the real fixture location, or the report
    # names files nobody can find.
    detail: list[str] = []
    for line in output.splitlines():
        if "-->" not in line:
            continue
        for stem, (name, lineno, src) in index.items():
            if stem in line:
                detail.append(f"  {name}:{lineno} — {src.strip()[:120]!r}")
    return "\n".join(offenders + ["", "Fixture locations:", *detail])


@pytest.fixture(scope="module")
def _candidates() -> list[tuple[str, int, str]]:
    sources = _embedded_python_sources()
    # Non-vacuity: if the collector stops finding embedded sources the gate goes
    # quiet without failing, which is the inert-control failure mode. The real
    # count is in the thousands; 500 is a floor that only a broken collector trips.
    assert len(sources) > 500, (
        f"collector found only {len(sources)} embedded Python sources under tests/ — "
        "expected thousands. The gate is not looking at anything; fix the collector "
        "rather than lowering this floor."
    )
    return sources


def test_no_embedded_fixture_uses_syntax_newer_than_the_minimum_python(
    _candidates: list[tuple[str, int, str]], tmp_path: Path
) -> None:
    """No fixture string may need a Python newer than the supported floor.

    This is the control for the class `ruff check .` structurally cannot see. It
    fires on any interpreter, so it does not depend on the 3.11 CI leg or on
    anybody remembering to read CI.
    """

    workdir = tmp_path / "embedded"
    workdir.mkdir()
    findings = _ruff_syntax_findings(_candidates, workdir)
    assert findings == "", (
        "an embedded source string in tests/ uses syntax newer than "
        f"{MIN_PYTHON_TARGET}. It will parse on the newest interpreter and raise "
        "SyntaxError on the oldest supported one, at test time, where only the "
        "matrix leg catches it (D-7(a); CLAUDE.md 'Boundaries and stack').\n\n"
        f"{findings}"
    )


def test_the_gate_catches_the_construct_that_actually_broke_ci(tmp_path: Path) -> None:
    """Plant the real defect and require the gate to refuse it.

    Without this, the suite above passes identically whether the mechanism works or
    ruff silently stopped reporting version-aware syntax errors — the exact
    "gate that cannot fail" shape found three times on this surface. It also pins
    the `requirements.txt` (`ruff>=0.6`) versus `constraints.txt` (`ruff==0.15.20`)
    gap: on a ruff too old for these diagnostics, this test fails loudly instead of
    the gate going quiet.
    """

    workdir = tmp_path / "planted"
    workdir.mkdir()
    findings = _ruff_syntax_findings(
        [("PLANTED", 0, _PLANTED_312_ONLY_SOURCE)], workdir
    )
    assert "invalid-syntax" in findings, (
        "the minimum-Python gate did NOT flag the PEP 701 nested-quote f-string "
        "that took CI red for seven commits. Either ruff no longer reports "
        f"version-aware syntax errors at --target-version {MIN_PYTHON_TARGET}, or "
        "the installed ruff predates that support (requirements.txt allows "
        "ruff>=0.6; constraints.txt pins the verified 0.15.20). The gate is inert "
        f"until this passes.\n\n{findings}"
    )


def test_the_planted_fixture_is_legal_on_this_file(tmp_path: Path) -> None:
    """This module must itself parse on the minimum Python.

    A gate against 3.12-only syntax that is written in 3.12-only syntax cannot run
    on the leg it protects. The planted construct is therefore built with differing
    inner quotes at module level and only assembles the illegal form inside a
    string — but that reasoning is worth asserting rather than trusting.
    """

    workdir = tmp_path / "selfcheck"
    workdir.mkdir()
    target = workdir / "this_module.py"
    shutil.copyfile(Path(__file__), target)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--target-version",
            MIN_PYTHON_TARGET,
            "--select=F401",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "invalid-syntax" not in (completed.stdout + completed.stderr), (
        "this gate module is not legal on the minimum supported Python, so it "
        "cannot run on the matrix leg it exists to protect:\n"
        f"{completed.stdout}\n{completed.stderr}"
    )


def test_collected_sources_are_reported_with_findable_locations(tmp_path: Path) -> None:
    """A failure must name the real file, not ruff's temp filename.

    The first version of this gate reported `f00042.py:2`, which is unactionable —
    a finding nobody can locate is a finding nobody fixes.
    """

    workdir = tmp_path / "locations"
    workdir.mkdir()
    findings = _ruff_syntax_findings(
        [("some_test_module.py", 123, _PLANTED_312_ONLY_SOURCE)], workdir
    )
    assert "some_test_module.py:123" in findings, (
        f"the failure report does not name the originating fixture:\n{findings}"
    )


def test_the_planted_construct_is_assembled_not_stored() -> None:
    """No string literal in THIS file may carry the illegal form.

    The tripwire is built by substituting the quote character at runtime,
    specifically so the collector finds nothing illegal here and the gate needs no
    self-exemption. Assert that rather than trusting it: someone simplifying this
    module back to a plain literal would make the gate fail on itself, and the
    obvious repair — an allowlist — reintroduces the evasion surface the
    append-caller gate was hardened against.
    """

    # The assembled value really is the nested-quote construct. Note the needle is
    # ALSO assembled: written as a literal it becomes an offender in its own right,
    # which is how the second draft of this test failed. Any file that discusses
    # this defect has to avoid spelling it.
    needle = "fQappend_{Qexecution_eventQ}Q".replace("Q", '"')
    assert needle in _PLANTED_312_ONLY_SOURCE

    # It is real Python on the CURRENT interpreter — so the tripwire is a genuine
    # version difference, not a typo that fails everywhere. (It must NOT raise here:
    # this runtime is 3.12+, where PEP 701 is legal. Its illegality at 3.11 is what
    # `test_the_gate_catches_the_construct_that_actually_broke_ci` asserts, via ruff,
    # which is the only check that works without a second interpreter.)
    compile(_PLANTED_312_ONLY_SOURCE, "<tripwire>", "exec", dont_inherit=True)

    # ...while no literal in this module that the COLLECTOR would pick up carries it.
    #
    # The filter matters and the third draft of this test got it wrong by omitting
    # it. This module's own docstring quotes the offending construct as an example,
    # deliberately — the explanation is worthless without it. That docstring is prose
    # wrapped around an indented snippet, so it does not parse as Python and the
    # collector skips it; it can never be an offender. Applying a stricter rule here
    # than the collector uses made this test fail on documentation, which would have
    # pushed the next maintainer toward deleting the example rather than keeping the
    # gate honest. Mirror the collector exactly: a literal is only dangerous if it
    # parses.
    prefix = "fQappend_{Q".replace("Q", '"')
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if prefix not in node.value:
            continue
        try:
            ast.parse(node.value)
        except (SyntaxError, ValueError, UnicodeEncodeError):
            continue  # prose or a partial snippet — the collector skips it too
        pytest.fail(
            f"line {node.lineno} stores the illegal construct in a literal that "
            "PARSES as Python, so the collector will flag it and this gate will "
            "fail on itself. Assemble it at runtime (see _PLANTED_312_ONLY_SOURCE) "
            "rather than adding a self-exemption."
        )


def test_a_lone_surrogate_fixture_does_not_crash_the_collector() -> None:
    """The collector must tolerate strings that cannot be UTF-8 encoded.

    `tests/` contains a deliberate lone-surrogate adversarial fixture. An earlier
    design serialized candidates to JSON and shelled out to a real `python3.11`;
    it died on that fixture before checking anything. The in-process collector
    skips it, which is why the two-interpreter design was rejected rather than
    debugged.
    """

    lone_surrogate = "\ud800"
    with pytest.raises((UnicodeEncodeError, ValueError, SyntaxError)):
        ast.parse(lone_surrogate)

    assert _embedded_python_sources(), "collector returned nothing over tests/"
