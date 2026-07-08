# Taste Engineering

Bias-correction discipline for landing pages, portfolios, and redesigns. Where `aesthetic-directions.md` gives you a visual point of view, this file gives you the engineering guardrails that keep an ambitious design from collapsing into AI slop: how to read a brief, how to calibrate variance/motion/density, when to install an official design system instead of hand-rolling CSS, the specific signatures that scream "a model made this," and a mechanical pre-flight pass.

Scope: marketing/landing/about/portfolio surfaces and redesigns of the same. NOT dashboards, data tables, multi-step forms, or admin UI (for those, reach for an official system per the map below and lean on `design-systems-reference.md`).

Every rule here is contextual. None of it fires automatically. Read the brief first, then pull only what fits.

> Insights distilled from production-tested anti-slop practice (designmd.co "taste skill") and adapted to this skill's workflow. Treat them as engineering constraints, not style opinions.

---

## 1. Read the brief before touching code

Most weak LLM design output comes from jumping to a default aesthetic instead of reading the room. Before code, infer:

1. **Page kind** - landing (SaaS / consumer / agency / event), portfolio (dev / designer / studio), redesign (preserve vs overhaul), editorial / blog.
2. **Vibe words** the user used - "minimalist", "Linear-style", "Awwwards", "brutalist", "premium consumer", "Apple-y", "playful", "serious B2B", "editorial", "glassy", "dark tech".
3. **Reference signals** - URLs, screenshots, products named, competitors. If they linked a site, run the `extraction-toolkit.md` flow. If they named a brand, check the `design-systems/` vault for its brief.
4. **Audience** - B2B procurement panel vs design-conscious consumer vs recruiter scanning a portfolio. The audience picks the aesthetic, not your taste.
5. **Existing brand assets** - logo, color, type, photography. For redesigns these are starting material, not optional (see Section 7).
6. **Quiet constraints** - accessibility-first, public-sector, regulated, trust-first commerce, kids' products. These OVERRIDE aesthetic preference.

### Output a one-line Design Read

Before any code, state it in one line:

> "Reading this as: `<page kind>` for `<audience>`, with a `<vibe>` language, leaning toward `<design system or aesthetic family>`."

Examples:

- "Reading this as: B2B SaaS landing for technical buyers, Linear-style minimalist, leaning Tailwind utilities + Geist + restrained motion."
- "Reading this as: solo designer portfolio for hiring managers, editorial / kinetic-type, leaning native CSS + scroll-driven animation + custom display type."

If the design read genuinely diverges, ask exactly **one** clarifying question (never a multi-question dump): "Should this feel closer to Linear-clean or Awwwards-experimental?" If you can confidently infer, do not ask. Declare the read and proceed.

**Anti-default discipline.** Do not reach for: AI-purple gradients, centered hero over dark mesh, three equal feature cards, glassmorphism on everything, infinite-loop micro-animations, Inter + slate-900. Those are the defaults. Reach past them deliberately.

---

## 2. The Three Dials

After the design read, set three dials. Every layout, motion, and density decision is gated by them. Use these exact names; do not invent aliases.

- **`DESIGN_VARIANCE` (1-10)** - 1 = perfect symmetry, 10 = artsy chaos
- **`MOTION_INTENSITY` (1-10)** - 1 = static, 10 = cinematic / physics
- **`VISUAL_DENSITY` (1-10)** - 1 = art gallery / airy, 10 = cockpit / packed data

**Baseline `8 / 6 / 4`** unless the read overrides. Overrides happen conversationally, never by asking the user to edit a config.

### Dial inference

| Signal                                                       | VARIANCE       | MOTION | DENSITY        |
| ------------------------------------------------------------ | -------------- | ------ | -------------- |
| minimalist / clean / calm / editorial / Linear-style         | 5-6            | 3-4    | 2-3            |
| premium consumer / Apple-y / luxury / brand                  | 7-8            | 5-7    | 3-4            |
| playful / wild / Dribbble / Awwwards / experimental / agency | 9-10           | 8-10   | 3-4            |
| landing page / portfolio / marketing (default)               | 7-9            | 6-8    | 3-5            |
| trust-first / public-sector / regulated / a11y-critical      | 3-4            | 2-3    | 4-5            |
| redesign - preserve                                          | match existing | +1     | match existing |
| redesign - overhaul                                          | +2             | +2     | match existing |

### What each dial means in code

- **VARIANCE 1-3:** symmetrical 12-col grid, equal padding, centered. **4-7:** offset overlaps (`margin-top: -2rem`), mixed aspect ratios, left-aligned headers over centered data. **8-10:** masonry, fractional grids (`grid-template-columns: 2fr 1fr 1fr`), large empty zones. **Mobile override:** levels 4-10 collapse to strict single column below `768px`.
- **MOTION 1-3:** `:hover`/`:active` only, no auto animation. **4-7:** fluid CSS transitions (`cubic-bezier(0.16, 1, 0.3, 1)`), `animation-delay` cascades, transform/opacity only. **8-10:** scroll-triggered reveals, parallax, scroll-driven animation. See Section 6.
- **DENSITY 1-3:** large gaps (`py-32`+), expensive whitespace. **4-7:** standard app spacing (`py-16` to `py-24`). **8-10:** tight padding, no card boxes, 1px lines separate data, `font-mono` for all numbers.

**Motion claimed = motion shown.** If `MOTION_INTENSITY > 4`, the page must actually move (hero entry, scroll-reveal on key sections, hover physics on CTAs at minimum). A static page claiming `7` is broken. If you cannot ship working motion in scope, drop the dial to 3 and ship a clean static page. Never half-build motion that breaks (cut-off ScrollTriggers, jumpy enters, missing cleanups).

---

## 3. Brief to design-system map

Do not invent CSS for things that have an official package. Do not pretend an aesthetic trend is an official system.

| Brief reads as...                         | Reach for             | Install                                                                             |
| ----------------------------------------- | --------------------- | ----------------------------------------------------------------------------------- |
| Microsoft / enterprise SaaS / dashboards  | Fluent UI             | `npm i @fluentui/react-components` (or `@fluentui/web-components @fluentui/tokens`) |
| Google-ish, Material-flavored product     | Material 3            | `npm i @material/web`                                                               |
| IBM-style B2B / enterprise analytics      | Carbon                | `npm i @carbon/react @carbon/styles`                                                |
| Shopify app surfaces                      | Polaris               | Polaris web components / Polaris React (required for Shopify admin)                 |
| Atlassian / Jira-style product            | Atlaskit              | `npm i @atlaskit/*` + `@atlaskit/tokens`                                            |
| GitHub-style devtool / community          | Primer                | `@primer/css` or `@primer/react-brand` (Brand variant for marketing)                |
| Public-sector UK service                  | GOV.UK Frontend       | `npm i govuk-frontend`                                                              |
| US public-sector / trust-first            | USWDS                 | `npm i uswds`                                                                       |
| Fast local-business / agency MVP          | Bootstrap 5.3         | boring, fast, works                                                                 |
| Modern accessible React foundation        | Radix Themes          | `npm i @radix-ui/themes`                                                            |
| Modern SaaS where you own components      | shadcn/ui             | `npx shadcn@latest add ...` (never ship default state)                              |
| Tailwind-based modern SaaS / AI marketing | Tailwind v4 + `dark:` | default for indie + small-team builds                                               |

**Honesty rules:**

- If the brief reads as a system above, install and use the **official** package. Do not recreate its CSS by hand. Do not import a system's tokens then override 90% of them.
- **One system per project.** No Fluent React with Carbon in the same tree; no shadcn components dropped into a Material app.
- When the brief is an **aesthetic, not a system** (glassmorphism, bento, brutalism, editorial, dark-tech, mesh gradients, kinetic type), there is no official package. Build with native CSS + Tailwind + a maintained component library, and label borrowed inspiration honestly in comments. Note specifically: there is no official `liquid-glass.css`; Apple Liquid Glass on the web is a `backdrop-filter` + layered-border approximation, label it as such.

---

## 4. Default architecture (when not using a system from Section 3)

- **Framework:** React / Next.js, Server Components by default. Any component using Motion, scroll listeners, or pointer physics is an isolated leaf with `'use client'` at the top. Server Components render static layouts only.
- **Styling:** Tailwind v4 default (use `@tailwindcss/postcss` or the Vite plugin, not the v3 `tailwindcss` PostCSS plugin). Tailwind v3 only if the project already demands it.
- **Animation:** Motion (formerly Framer Motion), import from `motion/react`.
- **Fonts:** `next/font`, or self-host with `@font-face` + `font-display: swap`. Never `<link>` Google Fonts in production.
- **State:** local `useState`/`useReducer` for isolated UI; Zustand/Jotai/context only to avoid deep prop drilling. **NEVER use `useState` for continuous input values** (mouse position, scroll progress, pointer physics, magnetic hover). Use Motion's `useMotionValue` / `useTransform` / `useScroll`. `useState` re-renders the tree every frame and collapses on mobile.
- **Icons:** one family per project from `@phosphor-icons/react`, `hugeicons-react`, `@radix-ui/react-icons`, or `@tabler/icons-react`. `lucide-react` only on explicit request. Never hand-roll SVG icon paths. Standardize `strokeWidth` globally.
- **Emoji:** discouraged in code/markup/visible text; replace with icon glyphs. Allowed only for an explicitly playful / chat / social vibe, used sparingly.
- **Layout mechanics:** standard breakpoints (`sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536`); contain pages with `max-w-[1400px] mx-auto` or `max-w-7xl`. Use `min-h-[100dvh]` for full-height heroes, never `h-screen` (iOS Safari address-bar jump). Use CSS Grid (`grid grid-cols-1 md:grid-cols-3 gap-6`), never flexbox percentage math (`w-[calc(33%-1rem)]`).
- **Dependency verification:** before importing any third-party library, check `package.json`. If missing, output the install command first. Never assume a library exists.

---

## 5. Layout discipline (hard rules)

Failing any of these is shipping broken work.

**Hero**

- Fits the initial viewport: headline max 2 lines desktop, subtext max 20 words AND max 3-4 lines, CTAs visible without scroll. If copy is too long, cut it or reduce scale, never overflow.
- Plan font scale and asset size together. Default `text-4xl md:text-5xl lg:text-6xl`; reach `text-6xl md:text-7xl` only for 3-5 word headlines. A 4-line hero headline is always a font-size error.
- Top padding max `pt-24` desktop. More and the content floats halfway down and reads as a bug.
- Max 4 text elements total: (eyebrow OR brand strip OR neither) + headline + subtext + CTAs (1 primary + max 1 secondary). Banned inside the hero: tagline below CTAs, trust micro-strip, pricing teaser, feature bullets, avatar row. Those move to sections below.
- "Used by / Trusted by" logo wall lives UNDER the hero as its own section, never in the hero flex row.
- The hero needs a real visual. Text + gradient blob is a placeholder, not a hero.

**Sections**

- **Eyebrow restraint** (the most-violated rule): max 1 eyebrow per 3 sections, hero counts as 1. If a section has one, the next 2 cannot. Mechanical check: count `uppercase tracking` micro-labels above headlines; fail if `count > ceil(sectionCount / 3)`. Best alternative to an eyebrow is dropping it; the headline alone is enough.
- **Split-header ban:** no "left big headline + right small explainer paragraph" as a section header. Stack headline over body (`max-w-[65ch]`) instead. Use the split only when the right column carries a real visual/interactive element.
- **Zigzag cap:** max 2 consecutive "image-left/text-right" then "text-left/image-right" sections. The 3rd consecutive image+text split fails. Break it with a full-width, vertical-stack, bento, or marquee section.
- **Section-layout-repetition ban:** a layout family appears at most once. An 8-section page uses at least 4 different families.
- **Bento:** exactly as many cells as you have content for (3 items -> 3 cells), no empty cells. Vary composition (do not stack 6 identical rows). At least 2-3 cells need real visual variation (image, brand gradient, pattern, tint), not all white-on-white text cards.
- **Navigation:** single line at desktop (condense, drop, or hamburger below `lg`); height 64-72px default, 80px max.

**Buttons, forms, consistency locks**

- **Button contrast (a11y):** every CTA text readable against its background, WCAG AA (4.5:1 body, 3:1 large 18px+). No white-on-white, no border-less transparent CTA over the page. Ghost buttons over photos need a scrim or stroke.
- **CTA wrap ban:** label fits one line at desktop. 3 words max for primary CTAs (ideally 1-2). Widen the button or shorten the label; never let it wrap.
- **No duplicate CTA intent:** "Get in touch" + "Let's talk" + "Start a project" are one intent. Pick one label, use it everywhere (nav, hero, footer). Same for signup and portfolio intents.
- **Forms:** label above input, helper text in markup, error text below, `gap-2` blocks. No placeholder-as-label, ever. Inputs, placeholders, focus rings, labels all pass WCAG AA against the section background.
- **Color consistency lock:** one accent color across the whole page. A warm-grey site does not get a blue CTA in section 7.
- **Shape consistency lock:** one corner-radius system (all-sharp, all-soft 12-16px, or all-pill for interactive). Mixed radii allowed only under a documented rule followed everywhere.
- **Page theme lock:** one theme (light, dark, or auto) for the whole page. No light-warm-paper section sandwiched between dark sections. Section-level tints within the same family are fine (`bg-zinc-950` next to `bg-zinc-900`); flipping to `bg-amber-50` mid-page is broken. The only exception is a deliberate, once-per-page "theme switch on scroll" device.

---

## 6. Motion and scroll

Motion must be motivated. Before adding any animation, answer in one sentence what it communicates: hierarchy, storytelling (sequenced reveal), feedback (acknowledging an action), or state transition. "It looked cool" is not an answer. GSAP everywhere because GSAP is available is amateur.

**Forbidden animation patterns:**

- `window.addEventListener("scroll", ...)` is a hard ban (runs every frame, jank-prone). Use Motion's `useScroll()`, GSAP `ScrollTrigger`, `IntersectionObserver`, or CSS `animation-timeline: view()`.
- Scroll-progress math in React state via `window.scrollY`, and `requestAnimationFrame` loops that touch React state. Use motion values instead.
- Marquee max one per page. Two reads as lazy filler.

**Library lanes:** Motion (`motion/react`) for UI/state-change motion; GSAP + ScrollTrigger for full-page scrolltelling and hijacks; Three.js/WebGL for canvas/3D. Isolate each in a dedicated `'use client'` leaf with `useEffect` cleanup. Never mix GSAP/Three.js with Motion in the same component tree, they fight over frames.

### Canonical scroll skeletons

These complement the interaction-classification work in `interaction-patterns.md`. Common failure for both pinned patterns: the trigger fires mid-scroll instead of pinning at the viewport top. Fix is always `start: "top top"` and `pin: true`.

**Sticky-stack** (cards pin and physically stack):

```tsx
"use client";
import { useRef, useEffect } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useReducedMotion } from "motion/react";

gsap.registerPlugin(ScrollTrigger);

export function StickyStack({ cards }: { cards: React.ReactNode[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce || !ref.current) return;
    const ctx = gsap.context(() => {
      const els = gsap.utils.toArray<HTMLElement>(".stack-card");
      els.forEach((card, i) => {
        if (i === els.length - 1) return;
        ScrollTrigger.create({
          trigger: card,
          start: "top top",
          endTrigger: els[els.length - 1],
          end: "top top",
          pin: true,
          pinSpacing: false,
        });
        gsap.to(card, {
          scale: 0.92,
          opacity: 0.55,
          ease: "none",
          scrollTrigger: {
            trigger: els[i + 1],
            start: "top bottom",
            end: "top top",
            scrub: true,
          },
        });
      });
    }, ref);
    return () => ctx.revert();
  }, [reduce]);
  return (
    <div ref={ref} className="relative">
      {cards.map((card, i) => (
        <div
          key={i}
          className="stack-card sticky top-0 min-h-[100dvh] flex items-center justify-center"
        >
          {card}
        </div>
      ))}
    </div>
  );
}
```

**Horizontal-pan** (vertical scroll drives horizontal travel): pin the wrapper, scrub the inner track, `end: () => '+=' + distance` where `distance = track.scrollWidth - window.innerWidth`, `start: "top top"`, `scrub: 1`, `invalidateOnRefresh: true`.

**Scroll-reveal stagger** (items appear on enter, no pinning): prefer Motion's `whileInView` over GSAP, it is lighter and needs no ScrollTrigger:

```tsx
"use client";
import { motion, useReducedMotion } from "motion/react";
export function RevealStagger({ items }: { items: string[] }) {
  const reduce = useReducedMotion();
  return (
    <ul className="grid gap-6">
      {items.map((item, i) => (
        <motion.li
          key={item}
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{
            duration: 0.6,
            delay: i * 0.06,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          {item}
        </motion.li>
      ))}
    </ul>
  );
}
```

Use reveal-stagger for feature lists, testimonial grids, logo walls. Save GSAP for real pin/scrub work.

**Guardrails:** animate only `transform` and `opacity`, never `top/left/width/height`. `will-change: transform` sparingly. Any motion above `MOTION_INTENSITY 3` honors `prefers-reduced-motion` (wrap with `useReducedMotion()`, or gate CSS behind `@media (prefers-reduced-motion: no-preference)`); infinite loops, parallax, scroll-hijack, and magnetic physics collapse to static under reduced motion. Apply grain/noise only on `fixed pointer-events-none` pseudo-elements, never on scrolling containers. Reserve z-index for systemic layers (nav, modal, overlay, grain), never spam `z-50`.

---

## 7. Redesign protocol

Misclassifying greenfield vs redesign is the biggest source of bad redesign output. Detect the mode first:

- **Greenfield** - no existing site, or full overhaul approved. Dial baseline from Section 2.
- **Redesign - preserve** - modernize without breaking the brand. Audit, extract tokens, evolve gradually.
- **Redesign - overhaul** - new visual language over existing content. Treat visuals as greenfield, preserve content and IA.

If ambiguous, ask once: "Should this redesign preserve the existing brand, or start visually from scratch?"

**Audit before touching:** document brand tokens (color, type, logo, radii), information architecture (page tree, nav, conversion paths), content blocks (what works vs filler), patterns to preserve (signature interactions, recognizable hero, copy voice), patterns to retire (slop tells, broken layouts, perf traps), the existing site's inferred dial values (your starting point, not the baseline), and the **SEO baseline** (ranking pages, meta titles, structured data, OG). SEO migration is the number-one redesign risk.

**Never change silently** (requires explicit approval): URL structure / route slugs, primary nav labels, form field names or order (breaks analytics + autofill), brand logo/wordmark, legal/consent/cookie copy. Extract brand colors before applying any palette rule (a brand that is already purple stays purple). Preserve copy voice unless a rewrite was asked for.

**Modernization levers (apply in order, stop when satisfied):** 1) typography refresh (biggest lift per unit risk), 2) spacing & rhythm, 3) color recalibration (desaturate, unify neutrals, keep brand accent), 4) motion layer, 5) hero & key-section recomposition, 6) full block replacement (only when unsalvageable). If IA/content/SEO are sound, prefer targeted evolution (levers 1-4): roughly 70% of the value at 40% of the risk.

---

## 8. AI Tells (forbidden by default)

These are the signatures a model defaults to when it tries to "look designed." Hard bans unless the brief explicitly calls for one. This list operationalizes the "sameness trap" warning in `SKILL.md`.

**Visual / CSS:** no neon or outer glows (use inner borders or tinted shadows); no pure `#000000` (off-black, zinc-950); no oversaturated accents; no gradient text on large headers; no custom mouse cursors.

**The AI-purple tell:** no automatic purple/blue button glows or random neon gradients. Use neutral bases (zinc/slate/stone) with one high-contrast accent (emerald, electric blue, deep rose, burnt orange). Embrace purple only when the brand explicitly asks, executed with intent.

**Premium-consumer palette ban** (the second most recurring tell): for cookware/wellness/artisan/luxury/heritage/DTC briefs, do not default-reach for warm beige/cream + brass/clay/oxblood/ochre + espresso text. Banned default families include backgrounds `#f5f1ea / #f7f5f1 / #fbf8f1 / #efeae0`, accents `#b08947 / #b6553a / #9a2436 / #9c6e2a`, text `#1a1714 / #1a1814`. Rotate instead: cold luxury (silver-grey + chrome), forest (deep green + bone + amber), black-and-tan, cobalt + cream, terracotta + slate, or pure monochrome + one saturated pop. Do not ship the same warm-craft palette twice in a row.

**Typography tells:** Inter as default (override only for neutral/Linear-style or public-sector); oversized H1s that just scream (control hierarchy with weight + color, not raw scale); serif as a default "creative" reach. **Serif discipline:** serif is very discouraged as default; the "creative brief = serif" instinct is the single most-tested AI tell. Use serif only when the brand names one, or the family is genuinely editorial/luxury/publication/heritage AND you can articulate why this serif fits this brand. `Fraunces` and `Instrument_Serif` are banned as defaults specifically. To emphasize a word in a headline, use italic or bold of the **same** font, never a random serif word injected into a sans headline. Italic display words with descenders (`y g j p q`) need `leading-[1.1]` min + `pb-1` reserve or they clip.

**Layout & spacing tells:** no three-column equal feature cards (use 2-col zigzag, asymmetric grid, scroll-pinned, or horizontal scroll); mathematically clean padding, no floating awkward gaps.

**Content & data ("Jane Doe" effect):** no generic names ("John Doe", "Sarah Chan"); no generic avatars (SVG egg, user-icon); no fake-perfect numbers (`99.99%`, `50%`, `1234567`) - use organic values; no startup-slop brand names ("Acme", "Nexus", "SmartFlow"); no filler verbs ("Elevate", "Seamless", "Unleash", "Next-Gen", "Revolutionize"). Fake-precise spec numbers (`92%`, `4.1x`, `5.8mm`) are banned unless from real data or labeled mock.

**Images:** no div-based fake product UI (fake task list / terminal / dashboard from styled divs) - this is the number-one tell; no hand-rolled decorative SVG illustrations as default; no broken Unsplash links (use `https://picsum.photos/seed/{descriptive-seed}/{w}/{h}` or a gen tool). Even minimalist sites need 2-3 real images; pure-text is incomplete work, not minimalism. For logo walls use real SVG marks (Simple Icons `https://cdn.simpleicons.org/{slug}/{color}`, or devicon), or a generated monogram for invented brands, never plain text wordmarks; logo wall = logos only, no category labels under each logo.

**Production-test tells (banned outright):**

- Version labels in the hero (`V0.6`, `BETA`, `INVITE-ONLY`, `EARLY ACCESS`) unless the brief is a launch.
- Section-number eyebrows (`00 / INDEX`, `001 . Capabilities`, `06 . how it works`) and `01 / 4` pagination on tiles. Eyebrows name the topic in plain language, never enumerate.
- The middle dot (`.`) as a default separator (max 1 per metadata line); decorative colored status dots before nav items / list rows / badges (zero by default, only for real semantic state).
- `<br>`-broken-and-italicized headlines; vertical rotated text; crosshair/hairline grid lines drawn purely as decoration.
- Poetic-craftsman labels ("From the field", "Field notes", "Currently on the bench", "Quietly trusted by"); mock-humble industry references; micro-meta sentences under eyebrows.
- Generic step labels ("Stage 1 / 2 / 3", "Phase 01 / 02"); use the verb-noun directly ("Install", "Configure", "Ship").
- Pills/labels overlaid on images (`Brand . 02`, `PLATE . BRAND`); photo-credit captions as decoration (`Field study no. 12 . Ines Caetano`) unless crediting a real photographer; version footers on marketing pages (`v1.4.2`, `Build 0048`); fake live counters ("Reservation 412 of 800").
- Hero-bottom decoration strips (`BRAND. MOTION. SPATIAL.`, `TYPE / FORM / MOTION`); floating top-right sub-text in section headings; scoring/progress bars with filled background tracks as comparison visuals.
- Locale/city/time/weather strips ("Lisbon 14:23 . 18C") for 99% of briefs; scroll cues (`Scroll`, the animated mouse-wheel icon) - if the user has not scrolled they are looking at the hero, they know what scroll is.
- `border-t` + `border-b` on every row of a long list / spec table. For more than 5 items reach for a different component (2-col split, card grid, tabs/accordion, scroll-snap pills, carousel, or 3-4 hero specs + a "view full specifications" disclosure), not a longer `<ul>`.

**Interactive states:** ship loading (skeletal loaders matching final shape, not generic spinners), empty (composed, shows how to populate), and error (inline for forms, toasts only for transient) states, not just the static success state. On `:active`, use `-translate-y-[1px]` or `scale-[0.98]` for tactile feedback.

### The em-dash ban

Em-dash (`-` long form) is **completely banned**, the single most-violated tell. No "limited use", no "in body copy is fine". Zero, everywhere visible: headlines, eyebrows, pills, button text, captions, body, quotes, attribution, nav, alt text. En-dash as a separator is banned too; ranges (`2018-2026`, `40-80k`) use a regular hyphen. The only permitted dash characters are the regular hyphen (`-`) and the minus sign in math (`-5C`). A single long dash anywhere visible fails pre-flight. (This matches the repo-wide rule in `CLAUDE.md`.)

---

## 9. Pre-flight check

Run before outputting code. If a box cannot be honestly ticked, it is not done.

- [ ] Design Read declared (one-liner, Section 1).
- [ ] Dial values explicit and reasoned, not silently baseline.
- [ ] Design system chosen from Section 3 if applicable, or aesthetic labeled honestly. One system per project.
- [ ] Redesign mode detected and audit performed if applicable (Section 7).
- [ ] **ZERO em-dashes** anywhere visible.
- [ ] Page theme lock, color consistency lock, shape consistency lock all hold.
- [ ] Hero fits viewport (headline <= 2 lines, subtext <= 20 words AND <= 4 lines, CTA visible, `pt-24` max, <= 4 text elements).
- [ ] Eyebrow count <= `ceil(sectionCount / 3)` (mechanical count of `uppercase tracking` labels).
- [ ] No split-header, no 3+ zigzag in a row, at least 4 layout families across 8 sections.
- [ ] Bento has rhythm AND exact cell count AND background diversity.
- [ ] Button contrast AA, no CTA wraps at desktop, no duplicate CTA intent, forms pass AA.
- [ ] Serif discipline (not Fraunces/Instrument_Serif unless justified; different from last project); italic descenders cleared.
- [ ] Premium-consumer palette is not the beige+brass+espresso default.
- [ ] Real images (gen tool, then Picsum seed, then labeled placeholder slots); no div fake screenshots, no hand-rolled decorative SVG, no pure-text minimalism. Logo wall = real SVG marks, logos only, under the hero.
- [ ] Copy self-audit: every visible string re-read, no broken/hallucinated phrases, no filler verbs, no Jane Doe / Acme.
- [ ] Motion motivated, marquee max one, motion-claimed = motion-shown, no `window.addEventListener('scroll')`, reduced-motion wrapped above dial 3, GSAP pins use `start: "top top"`.
- [ ] Dark mode tokens defined and tested in both modes (no pure black/white; brand stays recognizable; hierarchy parity).
- [ ] Mobile collapse explicit for high-variance layouts; `min-h-[100dvh]` not `h-screen`; `useEffect` animations have cleanup.
- [ ] Empty / loading / error states present; cards omitted in favor of spacing where possible; icons from an allowed library only.
- [ ] Core Web Vitals plausible: LCP < 2.5s (hero image `priority`/preloaded), INP < 200ms, CLS < 0.1.

---

## Out of scope

Not for dashboards, dense product UI, data tables, multi-step forms/wizards, code editors, native mobile, or realtime-collab UIs. If the brief is one of those, say so, point to the right tool (an official system from Section 3, TanStack Table / AG Grid for tables, Apple HIG / Material for native), and apply only this skill's marketing/about/landing parts to the surfaces where they fit.
