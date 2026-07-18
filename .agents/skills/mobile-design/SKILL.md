---
name: mobile-design
description: Platform design guidelines for building and evaluating apps across every major platform. Covers Apple HIG (iOS, iPadOS, macOS, watchOS, visionOS, tvOS), Material Design 3 (Android), and WCAG 2.2 + MDN (Web). Use when building, reviewing, or auditing mobile, desktop, or web interfaces for design compliance.
---

# Mobile Design Skill

A collection of platform design skills for building and evaluating apps across every major platform. Each sub-skill encodes the official design guidelines -- from Apple's Human Interface Guidelines to Google's Material Design to web standards -- into actionable rules AI agents can apply during code generation, review, and refactoring.

Built by scraping the [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines), [Material Design 3](https://m3.material.io), and [WCAG 2.2](https://www.w3.org/WAI/WCAG22/quickref/) then distilling them into succinct but exhaustive skill files.

**Source**: [ehmo/platform-design-skills](https://github.com/ehmo/platform-design-skills)

---

## Directory Structure

```
mobile-design/
|-- SKILL.md                # This file - master entry point
|
|-- i-os/
|   |-- i-os.md             # iPhone (Apple HIG) - 50+ rules
|
|-- ipad-os/
|   |-- ipad-os.md          # iPad (Apple HIG) - 35+ rules
|
|-- mac-os/
|   |-- mac-os.md           # Mac (Apple HIG) - 50+ rules
|
|-- watch-os/
|   |-- watch-os.md         # Apple Watch (Apple HIG) - 34 rules
|
|-- vision-os/
|   |-- vision-os.md        # Apple Vision Pro (Apple HIG) - 44 rules
|
|-- tv-os/
|   |-- tv-os.md            # Apple TV (Apple HIG) - 34 rules
|
|-- android/
|   |-- android.md          # Android (Material Design 3) - 50+ rules + dev skills index
|   |-- build/              # AGP 9 upgrade (from android/skills)
|   |-- jetpack-compose/    # XML-to-Compose migration (from android/skills)
|   |-- navigation/         # Navigation 3 with 20 recipes (from android/skills)
|   |-- performance/        # R8 keep rule analyzer (from android/skills)
|   |-- play/               # Play Billing Library upgrade (from android/skills)
|   |-- system/             # Edge-to-edge Compose (from android/skills)
|
|-- web/
|   |-- web.md              # Web (WCAG 2.2 + MDN) - 60+ rules
|
|-- chrome-webstore/
|   |-- chrome-webstore.md  # Chrome Web Store release automation blueprint
```

Each platform file is a single, self-contained reference that merges the full design guidelines, metadata, agent context, and section index into one document.

---

## Platforms

| Sub-skill         | Platform         | Source                                                                  | Guidelines Scope                                                                             |
| ----------------- | ---------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `i-os`            | iPhone           | Apple HIG                                                               | 50+ rules: navigation, layout, accessibility, gestures, Dynamic Island                       |
| `ipad-os`         | iPad             | Apple HIG                                                               | 35+ rules: multitasking, pointer, keyboard, Apple Pencil, Stage Manager                      |
| `mac-os`          | Mac              | Apple HIG                                                               | 50+ rules: menu bars, windows, toolbars, keyboard-driven, desktop UX                         |
| `watch-os`        | Apple Watch      | Apple HIG                                                               | 34 rules: glanceable design, Digital Crown, complications, Always On                         |
| `vision-os`       | Apple Vision Pro | Apple HIG                                                               | 44 rules: spatial layout, eye/hand input, volumes, immersive spaces                          |
| `tv-os`           | Apple TV         | Apple HIG                                                               | 34 rules: focus navigation, Siri Remote, 10-foot UI, Top Shelf                               |
| `android`         | Android          | Material Design 3 + [android/skills](https://github.com/android/skills) | 50+ design rules + 6 dev skills: AGP 9, XML-to-Compose, Nav3, R8, Play Billing, edge-to-edge |
| `web`             | Web              | WCAG 2.2 + MDN                                                          | 60+ rules: accessibility, responsive design, forms, performance, i18n                        |
| `chrome-webstore` | Chrome Web Store | CWS API docs                                                            | OAuth setup, release automation, CI publish workflows, status checks                         |

---

## When to Use

### iOS

- Building SwiftUI or UIKit interfaces for iPhone
- Reviewing iOS app code for HIG compliance
- Choosing between iOS navigation patterns
- Implementing accessibility, Dark Mode, Dynamic Type

### iPadOS

- Building iPad-optimized interfaces
- Implementing Split View, Slide Over, Stage Manager support
- Adding pointer/trackpad and keyboard shortcut support
- Designing responsive layouts for iPad screen sizes

### macOS

- Building macOS apps with SwiftUI or AppKit
- Implementing menu bars, toolbars, and sidebars
- Adding keyboard shortcuts and window management
- Designing for Catalyst or native macOS

### watchOS

- Building watchOS apps or complications
- Designing for small screens and short interactions
- Implementing health/fitness features on Watch

### visionOS

- Building visionOS apps with RealityKit or SwiftUI
- Designing for spatial computing and indirect gestures
- Implementing immersive experiences

### tvOS

- Building tvOS apps
- Implementing focus-based navigation with Siri Remote
- Designing for 10-foot viewing experiences

### Android

- Building Android apps with Jetpack Compose or XML layouts
- Reviewing Android code for Material Design compliance
- Implementing Material You and dynamic color
- Choosing between Android navigation patterns
- Upgrading AGP to version 9 (new DSL, built-in Kotlin, kapt-to-KSP)
- Migrating XML Views to Jetpack Compose
- Implementing or migrating to Navigation 3
- Analyzing R8/ProGuard keep rules for app size optimization
- Upgrading Google Play Billing Library
- Adding edge-to-edge support with system bar insets and IME handling

### Web

- Building web interfaces with any framework
- Auditing sites for accessibility compliance
- Implementing responsive, performant web layouts
- Reviewing web UI code for best practices

### Chrome Web Store

- Setting up Chrome extension release automation from scratch
- Walking through OAuth and refresh token setup for CWS API
- Wiring secrets into local env files and CI (GitHub Actions)
- Implementing version-triggered publish workflows
- Checking submission status (PUBLISHED, PENDING_REVIEW)

---

## Platform File Structure

Each platform has a single consolidated file containing:

- **YAML frontmatter** with name, description, and version
- **Full design guidelines** with numbered rules, code examples, and evaluation checklists
- **Metadata** including abstract, references, and source URLs
- **Section index** with rule IDs, severity levels, and cross-references
- **Agent context** including priority levels and "never do" lists (where applicable)

### Rule Severity Levels

- **CRITICAL** -- Must never be violated
- **HIGH** -- Follow unless there is a documented reason
- **MEDIUM** -- Recommended best practices

---

## Usage Examples

```
Review this SwiftUI view for iOS HIG compliance
```

```
Check this Android Compose screen against Material Design
```

```
Audit this web page for accessibility
```

```
Evaluate this iPad app for multitasking and pointer support
```

```
Review this watchOS complication for glanceable design principles
```

---

## Sources

- [Apple Human Interface Guidelines (2025)](https://developer.apple.com/design/human-interface-guidelines)
- [Material Design 3](https://m3.material.io)
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref)
- [MDN Web Docs](https://developer.mozilla.org)
