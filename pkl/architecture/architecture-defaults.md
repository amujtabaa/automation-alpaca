---
type: Architecture Knowledge
title: Architecture Defaults (seed)
status: draft
authority: low
owner: architect
last_verified: 2026-07-07
tags: [architecture, seed]
source_refs: []
supersedes: []
superseded_by: null
---

# Architecture Defaults (seed page)

> **Replace with this project's actual architecture.** This page is an
> installer seed marked `status: draft`. It becomes real only when this
> project's owners edit it and raise its authority.

Starting defaults many projects adopt (edit or delete freely):

- Modular monolith first; split services only under demonstrated need.
- Clean / Hexagonal boundaries between domain and infrastructure.
- Vertical slices for feature work.
- Business logic belongs in domain/application layers, not route handlers.
- Architecture changes require an accepted ADR.
