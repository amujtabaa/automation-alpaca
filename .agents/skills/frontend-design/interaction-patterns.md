# Interaction Patterns & Component Specification

Frameworks for classifying interactive behavior and writing component specifications before building. Use alongside SKILL.md (creative philosophy) and design-systems-reference.md (technical craft).

---

## 1. Interaction Model Classification

Before building ANY interactive component, classify its interaction model. This single decision prevents the most expensive frontend mistakes: building click-based tabs when the original is scroll-driven, or adding JavaScript to something that should be pure CSS.

### The Five Models

#### Static

No state changes. Pure layout and styling.

- **Examples**: Hero sections, footer, static cards, text blocks
- **Build approach**: Direct HTML/CSS, no JavaScript needed
- **Key signals**: No buttons, no scroll effects, no timed changes
- **Common mistake**: Adding unnecessary state or animations to content that should just render

#### Click-Driven

State changes triggered by discrete user actions (click, tap, keyboard).

- **Examples**: Tab panels, accordions, modals, dropdown menus, toggle switches
- **Build approach**: State management (`useState`/`useReducer`), event handlers, ARIA roles
- **Key signals**: Buttons, clickable elements, discrete state transitions with clear before/after
- **Common mistake**: Building as scroll-driven when tabs have explicit buttons. If users click to switch content, it is click-driven regardless of how smooth the transition looks.

#### Scroll-Driven

State changes triggered by scroll position or viewport intersection.

- **Examples**: Sticky headers that collapse on scroll, parallax effects, scroll-snap sections, viewport-entry animations, progress indicators
- **Build approach**: `IntersectionObserver`, scroll event listeners, CSS `scroll-snap`, `scroll-driven animations`
- **Key signals**: Elements that animate on scroll, sections that snap, content that reveals on viewport entry
- **Common mistake**: Building as click-driven tabs when sections actually scroll-snap between states. Observe the page by scrolling BEFORE clicking anything.

#### Time-Driven

State changes triggered by elapsed time.

- **Examples**: Auto-rotating carousels, countdown timers, loading sequences, typewriter effects, auto-dismissing toasts
- **Build approach**: `setInterval`/`setTimeout`, CSS `animation-delay`, `requestAnimationFrame`
- **Key signals**: Content that changes without user interaction, auto-advance behavior, timed sequences
- **Common mistake**: Missing pause-on-hover or pause-on-focus for accessibility. Time-driven components MUST pause when the user is interacting with them.

#### Hover-Driven

State changes triggered by pointer proximity or hover.

- **Examples**: Preview cards, tooltip reveals, image zoom, navigation mega-menus, cursor-following effects
- **Build approach**: CSS `:hover`, `onMouseEnter`/`onMouseLeave`, pointer tracking
- **Key signals**: Content that appears on hover, scale/transform changes, cursor-dependent behavior
- **Common mistake**: No keyboard/touch fallback. Hover-only interactions are invisible on mobile. Every hover-driven component needs a tap or focus equivalent.

### Classification Decision Framework

**Step 1: Observe before interacting.**
Scroll through the page slowly. Do not click anything yet. The number one mistake is building click-based tabs when the original is scroll-driven.

**Step 2: Ask these questions in order:**

1. Does anything change without user interaction? --> Time-driven
2. Does scrolling trigger visual changes? --> Scroll-driven
3. Do elements change on hover/pointer proximity? --> Hover-driven
4. Do elements change on click/tap? --> Click-driven
5. Nothing changes? --> Static

**Step 3: Check for compound models.**
Many real components combine models. Examples:

- **Carousel**: Time-driven (auto-advance) + Click-driven (manual nav dots) + Hover-driven (pause on hover)
- **Mega-menu**: Hover-driven (open on desktop) + Click-driven (mobile fallback)
- **Sticky header**: Scroll-driven (compact on scroll) + Click-driven (hamburger toggle)
- **Toast notification**: Time-driven (auto-dismiss) + Click-driven (manual dismiss) + Hover-driven (pause timer)

When compound, identify the PRIMARY model (the one that determines architecture and state shape) and SECONDARY models (layered on top as enhancement). Build the primary model first, then add secondary behaviors.

---

## 2. Component Specification Template

For any component rated "complex" (stateful, multi-breakpoint, animated, or interactive), write a spec file BEFORE dispatching a builder. If a builder has to guess anything, the spec has failed.

### When to Write a Spec

Write a spec when the component meets any of these criteria:

- Has 2+ interaction models
- Has 3+ responsive breakpoint changes
- Has stateful behavior (tabs, accordions, carousels)
- Has scroll-triggered animations
- Exceeds ~50 lines of estimated code

For simple static components (a card, a footer, a text section), skip the spec and build directly.

### Spec File Template

Save to `docs/components/<component-name>.spec.md` or include inline in the builder prompt.

```markdown
# Component: [Name]

## Overview

- **Target file**: `src/components/[name].tsx`
- **Interaction model**: [static | click-driven | scroll-driven | time-driven | hover-driven | compound]
- **Complexity**: [simple | moderate | complex]

## DOM Structure

[Semantic HTML outline with nesting, ARIA roles, and landmark elements]

## Visual Specifications

| Element   | Property       | Value     |
| --------- | -------------- | --------- |
| Container | background     | #ffffff   |
| Container | padding        | 48px 24px |
| Heading   | font-size      | 32px      |
| Heading   | font-weight    | 600       |
| Heading   | letter-spacing | -0.8px    |

## States and Behaviors

### [State Name, e.g., "Default to Active Tab"]

- **Trigger**: [click on tab button | scroll to section | after 3 seconds]
- **State A (before)**: [exact CSS values]
- **State B (after)**: [exact CSS values]
- **Transition**: `[property] [duration] [easing]`
- **Implementation**: [CSS transition | CSS animation | JS state change | IntersectionObserver]

## Responsive Behavior

| Breakpoint       | Changes                                              |
| ---------------- | ---------------------------------------------------- |
| Desktop (1440px) | Default layout                                       |
| Tablet (768px)   | Grid cols reduce, font sizes scale, elements reorder |
| Mobile (390px)   | Stacked layout, hamburger menu, 44px touch targets   |

## Assets

- Images: [list with paths and dimensions]
- Icons: [list with component names]
- Fonts: [any component-specific font requirements]

## Text Content

[Verbatim content: headings, body text, button labels, placeholder text]

## Dependencies

- [shadcn components needed]
- [hooks needed]
- [utility functions needed]
```

### Pre-Build Checklist

Before dispatching a builder with this spec, verify:

- [ ] Interaction model explicitly identified
- [ ] Every CSS value is exact (from `getComputedStyle` or design system), not estimated
- [ ] All states captured, not just the default
- [ ] Scroll triggers documented with before/after styles and thresholds
- [ ] Hover states include transition timing
- [ ] All images identified including layered compositions (background + foreground + overlay)
- [ ] Responsive behavior documented for all breakpoints
- [ ] Text content is verbatim, not paraphrased
- [ ] Builder prompt is under 150 lines (split if over)
- [ ] Dependencies listed explicitly

### Complexity Budget Rule

If a component spec exceeds ~150 lines, the component is too complex for one builder. Split it:

1. Identify natural boundaries (header, content area, footer, sidebar)
2. Create separate spec files for each sub-component
3. Create an assembly spec that imports and arranges the sub-components
4. Dispatch sub-component builders in parallel, then assemble

Example split for a pricing page:

```jsx
// Sub-component specs dispatched in parallel
<PricingHeader />    // Static: headline + subtitle
<PricingToggle />    // Click-driven: monthly/annual switch
<PricingCards />     // Click-driven: plan selection + hover states
<PricingFAQ />       // Click-driven: accordion
<PricingCTA />       // Static: bottom call-to-action

// Assembly spec: layout grid, spacing between sections, responsive stacking
```

---

## 3. Behavioral State Diffing

When analyzing a reference site or debugging animations, use this mechanical process to extract exact transition specifications. This removes guesswork and produces implementation-ready values.

### The Process

1. **Capture State A**: Record all CSS values in the default/initial state
2. **Trigger the change**: Scroll, click, hover, or wait for the time trigger
3. **Capture State B**: Record all CSS values in the changed state
4. **Diff the states**: Compare A and B to identify exactly which properties changed
5. **Record the transition**: Note duration, easing, delay, and which properties animate
6. **Record the trigger**: Scroll position, click target, hover element, or time threshold

### What to Capture Per State

Focus on properties most likely to change during interactions:

- `transform` (translate, scale, rotate)
- `opacity`
- `background-color`, `color`
- `height`, `max-height`, `width`
- `padding`, `margin`
- `border-color`, `border-width`
- `box-shadow`
- `font-size`, `font-weight`
- `position`, `top`, `left`
- `clip-path`
- `filter`, `backdrop-filter`

For comprehensive extraction from live sites, use the scripts in extraction-toolkit.md (Section 2: Component CSS Extraction, Section 4: Multi-State Extraction Workflow).

### Worked Example: Sticky Header Collapse

**Trigger:** Scroll position > 100px (IntersectionObserver on a sentinel element placed at the top of the page)

| Property        | State A (top) | State B (scrolled)         | Transition                     |
| --------------- | ------------- | -------------------------- | ------------------------------ |
| height          | 80px          | 56px                       | height 200ms ease-out          |
| padding         | 24px 32px     | 12px 32px                  | padding 200ms ease-out         |
| background      | transparent   | rgba(255,255,255,0.95)     | background 200ms ease-out      |
| backdrop-filter | none          | blur(12px)                 | backdrop-filter 200ms ease-out |
| box-shadow      | none          | 0 1px 3px rgba(0,0,0,0.08) | box-shadow 200ms ease-out      |
| logo font-size  | 24px          | 18px                       | font-size 200ms ease-out       |

**Implementation:**

```jsx
const [scrolled, setScrolled] = useState(false);

useEffect(() => {
  const sentinel = sentinelRef.current;
  const observer = new IntersectionObserver(
    ([entry]) => setScrolled(!entry.isIntersecting),
    { threshold: 0 }
  );
  observer.observe(sentinel);
  return () => observer.disconnect();
}, []);

// In JSX: a zero-height sentinel div at the top of the page
<div ref={sentinelRef} className="h-0" />

<header className={cn(
  "fixed top-0 w-full transition-all duration-200 ease-out",
  scrolled
    ? "h-14 py-3 bg-white/95 backdrop-blur-md shadow-sm"
    : "h-20 py-6 bg-transparent"
)}>
  <Logo className={cn(
    "transition-all duration-200",
    scrolled ? "text-lg" : "text-2xl"
  )} />
</header>
```

**Why IntersectionObserver over scroll listeners:** It is declarative, performs no work between intersections, and avoids scroll-jank from synchronous layout queries. Use a sentinel element (a zero-height div at the trigger point) instead of reading `window.scrollY`.

---

## 4. Integration Notes

- **With SKILL.md**: Use interaction model classification when committing to an aesthetic direction. Some aesthetics naturally favor certain models. Editorial designs lean scroll-driven (magazine-style reveals). Precision/utility designs lean click-driven (explicit controls). Playful designs often use hover-driven interactions. Choose models that reinforce the aesthetic rather than fighting it.
- **With design-systems-reference.md**: Animation timing values from Section 12 (Animation Guidelines) apply to all state transitions documented here. Use `--duration-fast` (100ms) for micro-interactions, `--duration-normal` (150ms) for state changes, `--duration-slow` (200ms) for larger transitions. Use `--ease-out` for most UI interactions.
- **With extraction-toolkit.md**: The CSS extraction scripts automate the State A/B capture process described in Section 3. When analyzing a reference site, use the Component CSS Extraction Script to capture computed values rather than eyeballing them. The Multi-State Extraction Workflow provides the exact steps for triggering changes and diffing results.

---

_Reference compiled: April 2025. Interaction classification framework adapted from JCodesMore/ai-website-cloner-template (MIT license)._
