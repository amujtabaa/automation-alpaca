# Aesthetic Directions

Complete aesthetic systems for frontend design. Pick one and commit fully. Mixing elements across directions produces the "AI slop" look. When the user's request doesn't name a direction, infer from their reference sites, brand, or audience. When nothing is specified, default to Brutally Minimal.

Use alongside SKILL.md (creative philosophy) and design-systems-reference.md (technical craft).

---

## Brutally Minimal

Minimalism here is an engineering discipline, not a visual preference. Every element earns its pixel. Shadow-as-border philosophy replaces traditional CSS `border` throughout: `box-shadow: 0 0 0 1px rgba(0,0,0,0.08)` avoids box model implications while creating cleaner edges. Content hierarchy emerges entirely from typography weight and spacing, never from color or decoration. The restraint IS the design. Every unit of whitespace is intentional negative space, not emptiness. Think Vercel, Resend, Raycast.

**Do:**

- Use shadow-borders (`box-shadow: 0 0 0 1px`) instead of CSS `border` for cards and containers
- Let typography weight alone drive hierarchy (500 for headings, 400 for body, nothing heavier)
- Use a single accent color sparingly, only for interactive elements
- Keep backgrounds at near-white (`#fafafa`) with pure white (`#ffffff`) for elevated cards
- Limit your palette to 4 total colors including black and white variants

**Don't:**

- Don't skip the inner `#fafafa` ring in card shadows. It creates the subtle glow that makes the system work
- Don't add decorative elements, gradients, or background textures. If you feel the urge, add more whitespace instead
- Don't use font weights above 600. Boldness contradicts the lightweight philosophy
- Don't use colored backgrounds for sections. Separation comes from spacing, not color blocks

**Quick Reference:**

- Colors: `#fafafa` (bg), `#ffffff` (card), `#171717` (text), `#666666` (muted), `#0070f3` (accent), `#eaeaea` (border)
- Font: Geist Sans 400/500, -0.02em tracking on headings, 1.6 line-height body
- Shadow: `0 0 0 1px rgba(0,0,0,0.08)` (card), `0 4px 12px rgba(0,0,0,0.05)` (hover)
- Radius: 6px (sm), 8px (md), 12px (lg)
- Spacing: 16px component gap, 32px section padding, 80-120px page sections

---

## Maximalist Chaos

Controlled disorder as creative statement. Layer competing visual systems: clashing type scales, overlapping elements, mixed media, aggressive color saturation. The chaos is curated. Every "random" element is placed with precise intention. Grids exist to be broken, but they must exist first. Without underlying structure, chaos becomes mess. The key is tension between order and disruption. Think Memphis Design, early Figma marketing pages, David Carson, 90s rave posters digitized.

**Do:**

- Establish a grid system first, then deliberately break it with overlapping elements at 10-30px offsets
- Use 3+ typefaces in a single composition (display, body, accent/decorative)
- Layer elements with negative margins and absolute positioning for controlled overlap
- Use saturated, clashing color combinations (hot pink + electric blue + acid yellow)
- Rotate text blocks at small angles (-3deg to 5deg) to break static layouts

**Don't:**

- Don't make everything random. The chaos needs at least 2-3 anchoring elements (consistent nav, readable body text)
- Don't use subtle pastels or muted palettes. This direction demands high saturation and high contrast
- Don't apply uniform spacing. Vary padding dramatically between sections (20px next to 120px)
- Don't use standard component patterns (clean cards, symmetric grids). Rethink every container
- Don't forget readability for body text. Chaos applies to composition, not to paragraph legibility

**Quick Reference:**

- Colors: `#ff2d87` (hot pink), `#00d4ff` (electric blue), `#ffed00` (acid yellow), `#7b2dff` (violet), `#0a0a0a` (ground), `#ffffff` (contrast)
- Font: Mix display (Space Mono, Archivo Black), body (DM Sans 400), accent (Permanent Marker, Rubik Glitch)
- Shadow: `8px 8px 0px #0a0a0a` (hard offset shadow, no blur)
- Radius: 0px (sharp) mixed with 50% (full circle). No in-between
- Spacing: Deliberately uneven. 20px, 48px, 120px, 16px in sequence

---

## Retro-Futuristic

Nostalgia for futures that never arrived. CRT scan lines, phosphor glow effects, monospace terminals mixed with sleek curves. The tension between vintage constraints (limited palettes, pixel grids, scan line artifacts) and modern capabilities (smooth gradients, backdrop-filter, GPU-accelerated glow) creates something that feels simultaneously old and impossibly advanced. Pair amber or green phosphor text-shadows on dark backgrounds with crisp vector geometry. Think Alien ship UI, Fallout Pip-Boy, Blade Runner terminals, TRON.

**Do:**

- Use monospace fonts (JetBrains Mono, IBM Plex Mono, Fira Code) as your primary display face
- Apply phosphor glow with layered `text-shadow`: `0 0 4px #00ff41, 0 0 12px #00ff4180, 0 0 24px #00ff4140`
- Add CRT scan line overlays using repeating-linear-gradient at 2-4px intervals with low opacity
- Use dark backgrounds (`#0a0f0a`, `#0d0208`) as the base. Light never dominates
- Include terminal-style UI elements: blinking cursors, typed-out text, command prompts, status bars

**Don't:**

- Don't use more than 2-3 colors per palette. Retro terminals had hardware color limits
- Don't apply the glow effect to body text. It destroys readability. Reserve it for headings and data highlights
- Don't use rounded, friendly shapes. Geometry here is angular, beveled, or hexagonal
- Don't mix retro elements with modern card/shadow patterns. Cards should look like terminal windows with borders, not floating surfaces
- Don't use serif or humanist fonts. Everything is monospace or geometric sans

**Quick Reference:**

- Colors: `#0a0f0a` (bg), `#00ff41` (green phosphor), `#ff6600` (amber phosphor), `#0affed` (cyan), `#1a1a2e` (panel), `#333333` (muted)
- Font: JetBrains Mono 400/700, 0.05em tracking on all text, 1.5 line-height
- Shadow: `0 0 4px #00ff41, 0 0 12px rgba(0,255,65,0.5)` (phosphor glow), `inset 0 0 30px rgba(0,0,0,0.5)` (CRT vignette)
- Radius: 0px (terminals are sharp) or 2px max for input fields
- Spacing: 12px tight grid, 24px panel padding, 1px borders everywhere (visible structure)

---

## Organic/Natural

Interfaces that breathe. Shapes flow with rounded, yielding edges. Borders dissolve into soft radii approaching pill and circle forms. The palette draws directly from earth: terracotta `#c67a4b`, sage `#87a878`, cream `#f5f0e8`, clay `#b5835a`, stone `#8b8680`. Animations mimic natural movement: gentle sway, leaf-fall easing curves, slow breathing scale pulses. Textures carry the weight of physical materials: paper grain, fabric weave, watercolor bleed edges. Nothing feels machined. Think Aesop, Patagonia, artisan ceramics studios.

**Do:**

- Use border-radius values of 16px+ for containers, approaching pill shapes (999px) for buttons and tags
- Apply subtle paper or grain texture overlays at 3-5% opacity on backgrounds
- Choose serif or humanist sans-serif fonts (Lora, Merriweather, Source Serif Pro, Nunito)
- Use organic easing curves: `cubic-bezier(0.34, 1.56, 0.64, 1)` for gentle bounces
- Keep color saturation low to medium. Earth tones, not neon

**Don't:**

- Don't use sharp corners or 0px border-radius anywhere. Even data tables get soft edges
- Don't use pure geometric shapes (perfect circles aside). Slight irregularity is welcome
- Don't use monospace or geometric sans-serif fonts. They feel mechanical
- Don't use harsh shadows with high opacity. Shadows should be warm-tinted and diffuse
- Don't use stark white (`#ffffff`) backgrounds. Warm off-whites (`#f5f0e8`, `#faf8f5`) only

**Quick Reference:**

- Colors: `#f5f0e8` (bg), `#2c2418` (text), `#c67a4b` (terracotta accent), `#87a878` (sage), `#b5835a` (clay), `#e8e0d4` (border), `#8b8680` (muted)
- Font: Source Serif Pro 400/600 headings, Nunito 400 body, -0.01em tracking, 1.7 line-height
- Shadow: `0 4px 16px rgba(139,100,60,0.08)` (warm diffuse), `0 2px 4px rgba(139,100,60,0.05)` (subtle)
- Radius: 16px (card), 24px (panel), 999px (button/tag)
- Spacing: 20px component, 40px section, 100-140px page sections, generous padding inside containers

---

## Luxury/Refined

Simultaneously technical and luxurious. Weight 300 headlines break convention: lightness equals confidence equals luxury. You are paying for what is NOT there. Generous negative space signals premium positioning. The color palette stays muted with a single surgical accent (gold `#b8860b`, deep navy `#0a1628`, burgundy `#722f37`). Chromatic shadows tinted with the brand's darkest neutral replace generic black shadows. Every interaction is smooth, deliberate, and slightly slower than expected, conveying that luxury takes its time. Think Stripe, Apple product pages, Bottega Veneta.

**Do:**

- Use font-weight 300 for headlines. This is the luxury voice. Weight 400 for body maximum
- Apply chromatic shadows tinted with brand color: `rgba(50,50,93,0.25)` not `rgba(0,0,0,0.25)`
- Allow 50-60% of the viewport to be empty space. Density is the opposite of luxury
- Use transitions of 300-500ms with ease-out curves. Luxury interfaces feel unhurried
- Limit your accent color to interactive elements and one hero moment per page

**Don't:**

- Don't use font-weight 600-700 for headlines. Bold text destroys the lightweight luxury system
- Don't fill empty space with decorative elements. The whitespace IS the luxury signal
- Don't use saturated or bright accent colors. Accent colors are deep, muted, and singular
- Don't use standard 200ms transitions. They feel cheap and abrupt in luxury contexts
- Don't stack multiple shadows. One sophisticated multi-layer shadow per elevation level

**Quick Reference:**

- Colors: `#fafafa` (bg), `#0a1628` (text/navy), `#525f7f` (muted), `#b8860b` (gold accent), `#f6f9fc` (card bg), `#e3e8ee` (border)
- Font: GT Super Display 300 headings, -0.03em tracking; system sans 400 body, 1.65 line-height
- Shadow: `0 6px 12px -2px rgba(50,50,93,0.25), 0 3px 7px -3px rgba(0,0,0,0.3)` (Stripe-style chromatic)
- Radius: 8px (card), 12px (modal), 6px (button), 4px (input)
- Spacing: 24px component, 48px section, 120-160px page sections

---

## Playful/Toy-like

Interfaces as interactive toys. Every element invites touch. Generous border-radius (12-24px) makes everything feel soft and squeezable. Bouncy spring animations on interactions: buttons squish on press, cards tilt on hover, elements wobble into view. Vibrant, saturated colors pulled from a toy box. Hand-drawn or illustrated elements mixed with clean UI. Micro-interactions on everything, because the fun IS the interface. Sound design opportunities at every click. Think Figma community pages, Notion emoji culture, Nintendo eShop, Duolingo.

**Do:**

- Use border-radius 12-24px on all containers. Buttons get 12px minimum, cards get 16-20px
- Add spring animations with overshoot: `cubic-bezier(0.175, 0.885, 0.32, 1.275)` for bouncy enters
- Use 5+ colors at full saturation. This is not the place for muted palettes
- Animate hover states: scale(1.02-1.05) with box-shadow increase on cards, translateY(-2px) on buttons
- Include illustrated or emoji-style accent elements where appropriate

**Don't:**

- Don't use sharp corners or small radius values. Nothing under 8px border-radius
- Don't use linear easing for animations. Everything bounces, springs, or overshoots slightly
- Don't use dark or muted color palettes. Playful means bright and saturated
- Don't use thin, delicate fonts. Round, bubbly, or chunky typefaces match the energy
- Don't over-animate navigation or critical actions. Playfulness applies to content, not to blocking UI

**Quick Reference:**

- Colors: `#6c5ce7` (purple), `#00cec9` (teal), `#fd79a8` (pink), `#fdcb6e` (yellow), `#00b894` (green), `#ffffff` (bg), `#2d3436` (text)
- Font: Nunito 600/700 headings, Nunito 400 body, 0em tracking, 1.6 line-height
- Shadow: `0 4px 0px #00000020` (hard bottom shadow), `0 8px 24px rgba(108,92,231,0.15)` (colored lift)
- Radius: 12px (button), 16px (card), 20px (panel), 999px (pill/tag)
- Spacing: 16px tight, 24px component, 48px section, generous inner padding (24-32px cards)

---

## Editorial/Magazine

Digital editorial as art direction. Chiaroscuro rhythm alternating dark panels against light panels creates dramatic pacing through the page. Typography leads everything: massive scale contrast between 72px+ headlines and 15-16px body text establishes the editorial voice. Strong vertical rhythm locked to a baseline grid keeps dense content feeling ordered. Pull quotes, drop caps (`:first-letter` styled at 3-4x body size), and full-bleed images break the text column. Asymmetric layouts with content offset from center create the magazine feel. Think Bloomberg Businessweek, NYT interactive features, Ferrari, Kinfolk.

**Do:**

- Use dramatic type scale: 64-80px headlines, 24-32px subheads, 15-16px body. The contrast IS the design
- Alternate between dark (`#1a1a1a` bg, `#f0ede8` text) and light (`#f0ede8` bg, `#1a1a1a` text) sections
- Implement drop caps with `:first-letter` pseudo-element at 3.5x body font size
- Use asymmetric grid layouts: content at 60% width offset to one side, images bleeding to edge
- Apply generous line-height (1.7-1.8) on body text. Editorial demands reading comfort

**Don't:**

- Don't use symmetric, centered layouts for content. Asymmetry creates the magazine feel
- Don't use small type scale contrast. If your headline is only 2x the body size, you lack editorial punch
- Don't skip the dark/light panel rhythm. A page of all-light sections reads as a blog, not a magazine
- Don't use UI-style components (cards with shadows, pill buttons) in editorial layouts. Use typography and whitespace
- Don't use sans-serif for body text. Serif body fonts are essential to the editorial identity

**Quick Reference:**

- Colors: `#1a1a1a` (dark panel), `#f0ede8` (light panel), `#c4372b` (editorial red accent), `#666666` (muted), `#ffffff` (highlight), `#333333` (secondary text)
- Font: Playfair Display 700 headings, -0.02em tracking; Source Serif Pro 400 body, 1.75 line-height
- Shadow: None. Editorial uses contrast and layering, not elevation shadows
- Radius: 0px everywhere. Sharp edges convey editorial authority
- Spacing: 24px paragraph, 64px between blocks, 120-180px section padding, full-bleed images at -margin

---

## Brutalist/Raw

Honest, confrontational, anti-design. The aesthetic IS the absence of aesthetic. System fonts (monospace preferred), raw HTML energy, visible structure. Borders are 1-2px solid black, not subtle shadows. No rounded corners (2px absolute maximum). Content sits directly on the page without decorative containers. Links are underlined because that is what links look like. Buttons have visible borders because that is what buttons look like. The design says: "I have nothing to hide." Think Craigslist elevated, Hacker News, Bloomberg Terminal, academic department sites done right.

**Do:**

- Use system monospace or Courier New as the primary typeface. This IS the brand voice
- Apply 1-2px solid borders on everything. Borders are structure, not decoration
- Keep backgrounds pure white (`#ffffff`) or pure black (`#000000`). No warm tints, no off-whites
- Display content in a single, narrow column (max-width 680px). Dense, readable, no sidebars
- Use underlines for links, visible outlines for focus states. Standard browser conventions

**Don't:**

- Don't add shadows of any kind. Shadows imply depth and polish, which contradict rawness
- Don't use border-radius above 2px. Rounded corners signal friendliness; brutalism rejects that
- Don't use custom fonts. System fonts and monospace stacks are the point
- Don't add background colors, gradients, or textures to sections. Content sits on flat white or flat black
- Don't animate anything. Static presentation is deliberate. Movement implies a desire to impress

**Quick Reference:**

- Colors: `#ffffff` (bg), `#000000` (text), `#0000ff` (links, classic web blue), `#ff0000` (accent/warning), `#888888` (muted), `#f0f0f0` (code bg)
- Font: `monospace` system stack, 400/700 only, 0em tracking, 1.5 line-height, 16px base
- Shadow: None. Zero shadows in the entire system
- Radius: 0px globally. 2px if you absolutely must soften an input field
- Spacing: 8px tight, 16px standard, 32px section, max-width 680px content column

---

## Art Deco/Geometric

Precision geometry as luxury. Strong bilateral symmetry anchors every layout. Repeated geometric motifs (chevrons, sunbursts, stepped forms, concentric circles) serve as ornament, replacing organic decoration. Gold and brass metallic accents (`#d4a853`, `#c9a84c`) shine against deep dark backgrounds (`#1a1520`, `#0d0b12`). Thin decorative lines (1px solid, often gold) and borders are the primary ornamental system. Typography features geometric letterforms: Futura, Avant Garde, Josefin Sans. The entire aesthetic is precision, symmetry, and restrained opulence. Think 1920s poster art digitized, Gatsby-era hotels, The Grand Budapest Hotel.

**Do:**

- Use geometric sans-serif fonts (Josefin Sans, Futura, Poiret One) for display text
- Apply thin decorative line borders (1px solid gold/brass) between sections and around containers
- Center everything. Bilateral symmetry is non-negotiable in Art Deco
- Use gold/brass accents (`#d4a853`) on dark backgrounds (`#1a1520`, `#0d0b12`) for the metallic feel
- Include geometric ornamental elements: chevron dividers, stepped borders, sunburst motifs using CSS

**Don't:**

- Don't use asymmetric layouts. Art Deco demands centered, symmetric composition
- Don't use thick, heavy borders. Lines are thin (1px) and elegant, never chunky
- Don't use warm or earthy colors. The palette is metallic gold, deep darks, cream, and selective jewel tones
- Don't use rounded or organic shapes. Geometry is angular: hexagons, triangles, chevrons, stepped forms
- Don't use casual or handwritten fonts. Typography is geometric and precise

**Quick Reference:**

- Colors: `#1a1520` (bg), `#d4a853` (gold accent), `#f5f0e0` (cream text), `#c9a84c` (brass), `#2a2035` (panel), `#8b7355` (muted gold)
- Font: Josefin Sans 300/400 headings, 0.15em tracking (wide); Raleway 400 body, 1.6 line-height
- Shadow: `0 0 20px rgba(212,168,83,0.15)` (gold glow), `inset 0 1px 0 rgba(212,168,83,0.1)` (inner shimmer)
- Radius: 0px for containers. 2px for buttons only. Geometry is angular
- Spacing: 32px component, 64px section, centered with 48px horizontal padding, symmetric always

---

## Soft/Pastel

Gentle, calming, approachable. The palette lives in low saturation: lavender `#e8dff5`, blush `#fce4ec`, mint `#e0f2f1`, butter `#fff9e6`, sky `#e3f2fd`. Generous padding wraps everything in visual comfort. Rounded corners and soft shadows at very low opacity create an interface that feels like touching something plush. No harsh contrasts anywhere. Even "black" text is actually dark gray (`#374151`). Light backgrounds only. The entire experience should lower the user's heart rate. Think Headspace, wellness apps, baby product brands, Notion's lighter moments.

**Do:**

- Use desaturated, pastel colors only. Test every color: if it looks vivid, reduce saturation by 30%
- Apply generous padding inside containers (24-32px) and between elements (20-24px)
- Use `#374151` or `#4b5563` for text instead of black. Dark gray maintains readability without harshness
- Keep shadows extremely light: max opacity 0.06. Shadows should barely be visible
- Use rounded corners 12-16px on all containers, 999px on buttons and badges

**Don't:**

- Don't use any color at full saturation. Even accents should be pastel variants
- Don't use pure black (`#000000`) or pure white (`#ffffff`) for text or backgrounds. Always off-variants
- Don't use dark mode or dark sections. This aesthetic only works on light, airy backgrounds
- Don't use heavy font weights above 600 for anything. The lightest weight that communicates hierarchy wins
- Don't add complex animations or bold motion. Transitions should be gentle fades and subtle slides

**Quick Reference:**

- Colors: `#faf8ff` (bg), `#374151` (text), `#e8dff5` (lavender), `#fce4ec` (blush), `#e0f2f1` (mint), `#d1c4e9` (border), `#7c6f9f` (accent muted purple)
- Font: Quicksand 400/500 or Poppins 300/400, -0.01em tracking, 1.65 line-height
- Shadow: `0 2px 8px rgba(0,0,0,0.04)` (card), `0 1px 3px rgba(0,0,0,0.03)` (subtle)
- Radius: 12px (card), 16px (panel), 999px (button/badge), 8px (input)
- Spacing: 20px component, 40px section, 80-120px page sections, 24-32px internal padding

---

## Industrial/Utilitarian

Function as aesthetic. Every pixel serves information delivery. Dense data display with no wasted space. The palette is muted and workmanlike: grays, khaki `#bdb76b`, dark olive `#556b2f`, steel `#708090`. Labels and metadata are treated as first-class content, not afterthought captions. Monospace for everything data-related. Grid lines are visible or strongly implied through borders and background alternation. The interface does not try to be beautiful. It tries to be useful, and beauty emerges from that honesty. Think military command dashboards, Bloomberg Terminal, factory control panels, aviation cockpits.

**Do:**

- Use monospace fonts for all data, labels, metrics, and status indicators
- Display dense information grids with minimal padding (8-12px cells)
- Show grid lines, borders, and structural dividers explicitly. No invisible grids
- Use alternating row backgrounds (`#f5f5f0` / `#ffffff`) for scanability in data tables
- Include status indicators, timestamps, and metadata in every data display

**Don't:**

- Don't add decorative whitespace. If space exists, fill it with useful information
- Don't hide labels or metadata behind hover states. All context is always visible
- Don't use vibrant or saturated accent colors. Status colors are muted: olive green (ok), amber (warning), rust (error)
- Don't round corners past 4px. Utilitarian interfaces are squared off
- Don't animate data changes with flashy transitions. Instant updates or subtle blink indicators only

**Quick Reference:**

- Colors: `#f5f5f0` (bg), `#1a1a1a` (text), `#556b2f` (olive/ok), `#b8860b` (amber/warning), `#8b3a3a` (rust/error), `#708090` (steel muted), `#e8e8e0` (border)
- Font: IBM Plex Mono 400/500 data, IBM Plex Sans 400 labels, 0em tracking, 1.4 line-height (tight)
- Shadow: `0 1px 2px rgba(0,0,0,0.05)` only on elevated panels. Most surfaces are flat
- Radius: 2px (button), 4px (panel), 0px (data cells, tables)
- Spacing: 8px cell padding, 12px component gap, 16px panel padding, 24px section divider
