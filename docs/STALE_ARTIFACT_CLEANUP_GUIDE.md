# Stale Artifact Cleanup Guide

## Purpose

Older implementation prompts are useful historical evidence, but they are not binding instructions for Spine v2 work unless a human explicitly reactivates them.

## Archive, do not delete

Move old implementation prompts from:

```text
docs/IMPLEMENTATION_PROMPT_*.md
```

to:

```text
docs/archive/legacy_implementation_prompts/
```

Add or preserve a README in that archive explaining that the files are historical and non-binding.

## Safe generated artifacts to delete

These can usually be deleted:

```text
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
dist/
build/
*.pyc
```

## Do not delete by default

Do not delete:

- source files;
- tests;
- current architecture docs;
- decision logs / ADRs;
- invariant registries;
- phase-named tests;
- old prompts that have been archived but remain useful as provenance.

## Stale link update rule

After archiving prompts, search for old references:

```bash
rg "docs/IMPLEMENTATION_PROMPT|IMPLEMENTATION_PROMPT_"
```

Update references that point to archived prompt files so they use:

```text
docs/archive/legacy_implementation_prompts/<filename>
```

Change only paths/comments unless a separate implementation task authorizes behavioral edits.
