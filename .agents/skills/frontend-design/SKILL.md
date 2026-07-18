---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, applications, dashboards, landing pages, forms, modals, sidebars, navbars, cards, or any UI element. Triggers on frontend design, styling, CSS, layout, responsive design, redesign, dark mode, theming, component libraries, and visual polish. Also use when the user shares a reference site to match or asks to improve the look of existing UI. Even if the user doesn't say "design", if they're building anything visual for the web, this skill applies.
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:

- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick a direction from `aesthetic-directions.md`. Each one is a complete system with philosophy, Do's/Don'ts, and ready-to-use values. When the user doesn't specify, infer from their reference sites, brand, or audience. Default to Brutally Minimal.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

For landing pages, portfolios, and redesigns, state a one-line **Design Read** before any code ("Reading this as: `<page kind>` for `<audience>`, with a `<vibe>` language, leaning toward `<system or aesthetic>`") and set the three dials (`DESIGN_VARIANCE` / `MOTION_INTENSITY` / `VISUAL_DENSITY`). See `taste-engineering.md`. If the brief names a known brand, check the `design-systems/` vault for its design brief first.

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work -- the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:

- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Available Directions

Pick one from `aesthetic-directions.md` and commit fully. Mixing across directions produces the "AI slop" look.

| Direction              | Personality                                                      | Think...                     |
| ---------------------- | ---------------------------------------------------------------- | ---------------------------- |
| Brutally Minimal       | Engineering restraint, shadow-borders, typography-only hierarchy | Vercel, Resend               |
| Maximalist Chaos       | Controlled disorder, clashing scales, grid-breaking              | Memphis Design, David Carson |
| Retro-Futuristic       | CRT glow, monospace terminals, phosphor on dark                  | Alien UI, Blade Runner       |
| Organic/Natural        | Earth tones, flowing shapes, paper textures                      | Aesop, Patagonia             |
| Luxury/Refined         | Weight 300 headlines, chromatic shadows, vast whitespace         | Stripe, Apple                |
| Playful/Toy-like       | Bouncy springs, saturated colors, generous radius                | Duolingo, Nintendo           |
| Editorial/Magazine     | Chiaroscuro panels, dramatic type scale, drop caps               | Bloomberg, Ferrari           |
| Brutalist/Raw          | System monospace, solid borders, anti-decoration                 | Hacker News, Craigslist      |
| Art Deco/Geometric     | Gold on dark, bilateral symmetry, geometric motifs               | Gatsby-era, Grand Budapest   |
| Soft/Pastel            | Low saturation, generous padding, dark-gray-not-black text       | Headspace, wellness apps     |
| Industrial/Utilitarian | Dense data, monospace labels, visible grid lines                 | Bloomberg Terminal, cockpits |

## Frontend Aesthetics Guidelines

Focus on:

- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Codex is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

## Gotchas

Common AI design failures that apply regardless of aesthetic direction:

- **The "sameness" trap**: Codex defaults to Inter/Geist + purple accent + white bg + 8px radius on everything. If your output looks like it could be any SaaS landing page, you haven't committed to a direction. Check aesthetic-directions.md and use the exact Quick Reference values.
- **Mixing aesthetics**: Using Stripe's chromatic shadows with Linear's luminance stepping. Each direction is a complete system. Don't cherry-pick across them.
- **Pure black/white**: Almost no real design system uses `#000000` or `#ffffff`. Use near-blacks and near-whites from design-systems-reference.md's Near-Black and Brand Neutrals section.
- **Ignoring letter-spacing at display sizes**: Headlines at 48px+ need negative tracking (-1.2px to -2.4px). Without it, large text looks loose and amateurish. See Progressive Letter-Spacing in design-systems-reference.md.
- **Bold everything**: AI agents default to weight 700 for emphasis. Most sophisticated design systems cap at 600 (many at 400). Check Weight Ceiling Rules before reaching for bold.
- **Shadow soup**: Applying `box-shadow` without understanding why each layer exists. Shadows have architectural purpose (border ring, lift, ambient, spread). See Named-Purpose Shadow Layers in design-systems-reference.md.
- **Forgetting hover/focus states**: Building the default state and shipping. Every interactive element needs visible hover, focus-visible, and active states. Check accessibility-requirements.md.
- **Building click tabs when it should be scroll-driven**: The #1 interaction mistake. Always classify the interaction model first. See interaction-patterns.md.
- **Em-dashes anywhere visible**: The single most-violated AI tell. `—` and `–` are banned in headlines, eyebrows, pills, body, quotes, attribution, captions, buttons, and alt text. Use a regular hyphen, comma, or period. See the em-dash ban in `taste-engineering.md`.
- **Breaking the consistency locks**: One accent color, one corner-radius system, and one theme (light/dark/auto) per page. A blue CTA on a warm-grey page, square cards with pill buttons, or a light section sandwiched in a dark page all read as broken. See `taste-engineering.md` Section 5.
- **Eyebrow-on-every-section**: The templated `uppercase tracking` micro-label above every headline produces the same AI rhythm. Cap at one per three sections (hero counts as one). See `taste-engineering.md`.
- **Fake screenshots and placeholder slop**: Div-based fake product UI, hand-rolled decorative SVGs, "Jane Doe"/"Acme" names, fake-perfect numbers, and pure-text "minimalism" are tells. Use real or generated images and believable content. See AI Tells in `taste-engineering.md`.

## Companion Files

Read the relevant companion file when the condition applies:

- `aesthetic-directions.md` -- Read when: choosing a visual direction, or when the user names a specific aesthetic (minimal, luxury, editorial, brutalist, etc.)
- `design-systems-reference.md` -- Read when: building enterprise SaaS, admin panels, developer tools, or any precision-focused interface. Also read for typography scales, shadow systems, dark mode implementation, or shadcn/Tailwind CSS theming.
- `accessibility-requirements.md` -- Read when: building any interactive component, form, modal, or navigation. Also read before shipping any interface to verify focus states, keyboard nav, ARIA, and contrast.
- `dashboard-visual-hierarchy.md` -- Read when: building dashboards, data displays, KPI cards, status indicators, or any interface where color directs attention to data.
- `interaction-patterns.md` -- Read when: building interactive components (tabs, carousels, sticky headers, accordions) or when you need to write a component spec before dispatching a builder agent.
- `extraction-toolkit.md` -- Read when: the user shares a reference URL to match, wants to analyze a live site's design system, or needs to extract CSS/fonts/colors from an existing page via Browser MCP.
- `taste-engineering.md` -- Read when: building a landing page, portfolio, marketing site, or redesign. Covers the Design Read + three dials, when to install an official design system (Fluent/Carbon/Polaris/Radix/shadcn) vs build an aesthetic, layout hard-rules, the production-test AI Tells, the redesign protocol, canonical scroll skeletons, and the pre-flight checklist.
- `design-systems/` -- A vault of 620 public brand design systems (`index.md` to browse, `systems.json` to grep). Read when: the user names a brand to emulate, or you want real-world reference for a palette/type/geometry choice. Each entry is a one-paragraph brief with a live URL; fetch the URL for the full spec when a build commits to a system. See `design-systems/index.md` for the usage flow.
