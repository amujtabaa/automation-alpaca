"""Regression pins for AI Project OS autonomy and escalation policy."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_machine_readable_autonomy_policy_is_fail_closed() -> None:
    rules = yaml.safe_load(_text(".ai-os/rules/prompt-rules.yaml"))
    policy = rules["runtime_rules"]["execution_autonomy"]

    assert policy["activated_scope_authorizes_reversible_execution"] is True
    assert policy["repeat_permission_requests_for_granted_scope"] is False
    assert policy["investigate_before_needs_input"] is True
    assert policy["failed_attempts_trigger_regate_before_human_escalation"] is True
    assert policy["fixed_named_model_escalation_required"] is False
    assert policy["human_input_required_for"] == [
        "human_gated_surface_without_recorded_approval",
        "destructive_or_irreversible_action_without_recorded_approval",
        "material_scope_or_authority_expansion",
        "unresolved_authority_or_architecture_conflict",
        "unavailable_external_secret_credential_or_human_decision",
    ]


def test_autonomy_policy_reaches_canonical_and_runtime_entrypoints() -> None:
    required_markers = {
        ".ai-os/core/06_FABLE_V3_EXECUTION_PROTOCOL.md": "## Autonomy and persistence",
        ".ai-os/templates/fable-core-v3.md": "## Autonomy and persistence",
        ".ai-os/core/19_AUTONOMY_AND_ESCALATION.md": "# Autonomy and Escalation",
        "CLAUDE.md": "## Autonomy and escalation",
        "AGENTS.md": "## Autonomy and escalation",
        ".claude/skills/fable/SKILL.md": "## Persistence and escalation",
        ".claude/commands/build.md": "### Persistence and permission discipline",
        ".claude/commands/team-build.md": "### Persistence and permission discipline",
        ".claude/commands/workflow-build.md": "### Persistence and permission discipline",
        ".claude/skills/session-management/SKILL.md": "## Cross-cutting autonomy rule",
        ".claude/skills/session-management/session-types/development.md": "### Blocker triage",
        ".claude/skills/session-management/session-types/debugging.md": "## Re-gate rule",
    }

    for relative, marker in required_markers.items():
        assert marker in _text(relative), f"{relative} lacks {marker!r}"


def test_obsolete_unconditional_stop_and_reapproval_rules_are_removed() -> None:
    stale_phrases = {
        "CLAUDE.md": "Plans always **pause for human approval**; no auto-execution, no auto-advance.",
        ".ai-os/templates/prompts/00_prompt-router.md": (
            "If the agent encounters surprise scope, stop and reroute."
        ),
        ".ai-os/templates/prompts/debugger.md": (
            "No fourth patch attempt. After three failed attempts, stop and return BLOCKED"
        ),
        ".claude/skills/session-management/session-types/development.md": (
            "On blockers: stop immediately, document, ask user."
        ),
    }

    for relative, stale in stale_phrases.items():
        assert stale not in _text(relative), f"obsolete rule remains in {relative}"


def test_named_model_ladder_is_not_a_runtime_requirement() -> None:
    live_policy_paths = (
        "CLAUDE.md",
        "AGENTS.md",
        ".ai-os/core/08_WORKTREES_AND_MODEL_ORCHESTRATION.md",
        ".ai-os/core/19_AUTONOMY_AND_ESCALATION.md",
        ".ai-os/templates/prompts/00_prompt-router.md",
        ".claude/skills/fable/SKILL.md",
    )

    for relative in live_policy_paths:
        assert "Terra" not in _text(relative)
    assert "No mandatory named-model ladder" in _text(
        ".ai-os/core/08_WORKTREES_AND_MODEL_ORCHESTRATION.md"
    )
