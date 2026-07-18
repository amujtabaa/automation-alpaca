# Blog Setup Playbook (One-Shot, Self-Contained)

> Stand up a production-grade blog on Fumadocs in any Next.js project in one pass.
> Everything needed ships in this skill: this playbook + the complete working implementation in `templates/`.
> Companion docs: `port-error-catalogue.md` (13 known failure modes), `centralized-meta-system.md`, `frontmatter-template.md`.

## The Architecture (read this first)

This is a two-layer design that makes a documentation framework look and behave like a blog:

- **Blog overlay** at `/blog`: a custom landing page inside the site's marketing layout (a route group like `(home)`). Animated switching headline + search, "Popular" sort, section/category filters, and a paginated card grid of all posts. ISR with `revalidate = 7200`. Organization + Blog JSON-LD for SEO.
- **Docs layer** at `/blog/[...slug]`: Fumadocs `DocsLayout` renders the posts themselves: sidebar with colored root-folder tabs, clerk-style table of contents, hardened SEO metadata, dynamic OG images, Article + Breadcrumb JSON-LD.
- **The trick**: both layers share the `/blog` URL prefix. There is deliberately NO `page.tsx` inside `app/blog/` -- the overlay page in the route group owns `/blog`, the docs layer owns everything deeper. This is what makes a docs framework feel like a blog.
- **Centralized meta system**: `blog-structure.ts` is the single source of truth for navigation. A script generates git-ignored `meta.json` files from it, content-collections ingests them, and the fumadocs loader builds the sidebar tree. You never hand-edit meta.json.

## Step 0: Prerequisites

- Next.js 15/16 App Router project with React 19, **Tailwind 4**, and shadcn/ui initialized (the blog components use `badge`, `button`, `card`, `input`, `select`, `skeleton` -- run `npx shadcn add badge button card input select skeleton` if missing).
- `@/*` import alias (adjust imports if your alias differs).
- For an older Tailwind 3 project, see the Tailwind 3 / fumadocs 14 appendix at the bottom.

## Step 1: Dependencies

Merge `templates/package-additions.jsonc` into your package.json. EXACT PINS, no carets -- caret ranges are how blog implementations silently drift across breaking majors (catalogue #3). Then install.

## Step 2: Copy the templates

Copy the entire `templates/src`, `templates/scripts`, and `templates/content-collections.ts` into your repo, preserving paths:

| Template                                                                                                 | Destination                | What it is                                                                                                                                   |
| -------------------------------------------------------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `content-collections.ts`                                                                                 | repo root                  | Collections + the frontmatter contract (menu/title/seoTitle/description/publishedAt/views) and the transform that maps `menu` to the sidebar |
| `scripts/generate-meta.ts`                                                                               | `scripts/`                 | Generates meta.json from blog-structure.ts                                                                                                   |
| `scripts/views-pull.ts`, `views-push.ts`                                                                 | `scripts/`                 | Views ops: pull counts from frontmatter to a master yaml, push edited yaml back                                                              |
| `src/content/blog/blog-structure.ts`                                                                     | same                       | Navigation single source of truth (EDIT: your sections)                                                                                      |
| `src/content/blog/guide/*.mdx`                                                                           | same                       | Example posts demonstrating the frontmatter contract                                                                                         |
| `src/config/paths.ts`                                                                                    | same                       | `DOCS_PREFIX = "/blog"`                                                                                                                      |
| `src/app/source.tsx`                                                                                     | same                       | Fumadocs loader + lucide icon resolver                                                                                                       |
| `src/app/blog/layout.tsx` + `layout.config.tsx`                                                          | same                       | DocsLayout wiring: nav, 340px sidebar, colored tab icons                                                                                     |
| `src/app/blog/[...slug]/page.tsx`                                                                        | same                       | The post page: JSON-LD, OG cache busting, seoTitle chain, robots, canonical, category grid                                                   |
| `src/app/api/og/[...slug]/route.tsx`                                                                     | same                       | Dynamic OG images with long-title font scaling                                                                                               |
| `src/app/(home)/blog/page.tsx`                                                                           | your marketing route group | The blog overlay landing page                                                                                                                |
| `src/components/blog/*` (7 files)                                                                        | same                       | Card, list, listing, query, search, heading, category components                                                                             |
| `src/components/filters/filters.tsx`, `src/components/pagination.tsx`, `src/contexts/filter-context.tsx` | same                       | Filter/pagination plumbing the listing depends on                                                                                            |
| `src/lib/blog-data.ts`, `blog-schema.ts`                                                                 | same                       | Search/sort/filter backend over fumadocs pages + nuqs URL params                                                                             |
| `src/lib/metadata.ts`, `schema.ts`                                                                       | same                       | SEO metadata builder + JSON-LD generators (Organization/Article/Blog/Breadcrumb)                                                             |
| `src/lib/utils/content.ts`, `docs.ts`                                                                    | same                       | Git lastModified, mirror docs, page-tree helpers                                                                                             |

Then merge `templates/globals-blog.css` into your `globals.css` (it is sectioned: imports, theme bridge, tab colors, sidebar styling, layout, content polish).

Add to `.gitignore`: `src/content/blog/**/meta.json`

Wrap your root layout's children in `RootProvider` from `fumadocs-ui/provider` if not already present.

**OG font (optional)**: the OG route accepts a `fonts` array. Either drop a `.woff` file next to the route and load it with `readFileSync` (see the route file comment), or delete the `fonts` option to use the default.

## Step 3: Brand it (find every TODO)

Every spot that must change is marked `TODO:` in the templates. Run a search for `TODO:` across the copied files and resolve each one. The complete list:

1. `src/lib/metadata.ts` -- SITE_NAME, default title/description, production domain in the localhost OG guard
2. `src/app/blog/[...slug]/page.tsx` -- the description brand prefix (`"Acme | "`), author name
3. `src/app/(home)/blog/page.tsx` -- blog title/description/copy, social profile links
4. `src/app/api/og/[...slug]/route.tsx` -- background hex (use your DARK theme background), logo SVG (simple paths only -- `next/og` cannot render foreignObject or external images), brand accent color
5. `src/app/blog/layout.config.tsx` -- your nav logo component
6. `src/components/blog/blog-heading.tsx` -- the TOPICS word-rotation array
7. `src/components/blog/blog-card.tsx` -- the section-to-icon switch (one case per root folder)
8. `src/content/blog/blog-structure.ts` -- your actual sections
9. `globals-blog.css` section 3 -- one `--<folder>-color` variable per root folder, light + dark. Folder names must match exactly: the tab transform reads `hsl(var(--<folder>-color))`
10. Global search for `Acme` and `acme.com` to catch anything remaining

CTAs: the post page template ships without promo CTAs. If you sell something, add your CTA card to the `tableOfContent.footer` and a mobile block (`xl:hidden`) below the description -- both locations are marked in the post page.

## Step 4: Verify (run ALL of these before calling it done)

- [ ] `pnpm generate:meta` -- one meta.json per section generated
- [ ] `pnpm build:content` -- all collections build, no schema errors
- [ ] `pnpm build` -- production build green; route list shows `/blog` (overlay), `/blog/[...slug]` (SSG), `/api/og/[...slug]`
- [ ] Dev render `/blog`: heading animates, cards render, search + Popular sort + section filter work
- [ ] Open a post: sidebar tabs show COLORED icons (inspect one in devtools -- the computed color must resolve, not be empty; catalogue #6), clerk TOC on the right, H1 = `title` frontmatter, sidebar label = `menu`
- [ ] OG image renders at `/api/og/<section>/<slug>/og.png` -- test one post with a 70+ character title to confirm font scaling
- [ ] View page source on a post: Article + Breadcrumb JSON-LD blocks, canonical link, `robots index,follow`, meta description has your brand prefix, `<title>` has NO site-name suffix
- [ ] `pnpm views:pull` writes the master yaml; edit a value; `pnpm views:push`; Popular sort reorders
- [ ] All files LF line endings (`.gitattributes` with `* text=auto eol=lf`); on Windows run dos2unix over copied files (catalogue #7)
- [ ] After deploy: re-check the post page sidebar on PRODUCTION, and run the CSS health check from catalogue #12 -- the most dangerous failure mode is styles that work locally and purge in the build container

## The SEO Title System (why the frontmatter has three title fields)

- `menu` -- sidebar label. Short (<=30 chars).
- `title` -- the H1 on the page AND the search-result title. Up to ~80 chars.
- `seoTitle` -- optional override used by search engines ONLY when `title` exceeds 60 chars (Google truncates around there).
- Page `<title>` carries NO site-name suffix (`SITE_NAME_TEMPLATE = "%s"`): every character of the 60 goes to the headline. Brand visibility moves to the meta description instead, which is auto-prefixed `"<Brand> | "` at render.
- These four pieces (schema, transform, post page, posts) are one atomic contract -- never change one without the others (catalogue #9).

## AI Content Workflow (per post, after setup)

1. Write MDX with frontmatter: `menu`, `title`, optional `seoTitle`, `description` (<=140 chars), `publishedAt: "YYYY-MM-DD"`, optional `views` seed (~2000 makes new posts rank reasonably in Popular sort).
2. Register the slug in `blog-structure.ts` (separator entry is exactly `"------"`).
3. `pnpm generate:meta`, then verify locally: sidebar entry, landing card, OG image.
4. Deploy, then submit the URL to search engines for indexing.
5. Periodically: `views:pull`, update counts from your analytics, `views:push`.

## Monorepo Mapping

The templates use a single-app layout. For a pnpm/turbo monorepo:

| Single-app (templates)          | Monorepo                                                                                                                                                                                                                                                                                                                    |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/...`                       | `apps/web/src/...`                                                                                                                                                                                                                                                                                                          |
| `content-collections.ts` (root) | `apps/web/content-collections.ts`                                                                                                                                                                                                                                                                                           |
| `scripts/`                      | `apps/web/scripts/`                                                                                                                                                                                                                                                                                                         |
| `.gitignore` entry              | prefix with `apps/web/`                                                                                                                                                                                                                                                                                                     |
| package.json build chain        | ALSO add a turbo task: `build:content` with inputs `["src/content/blog/blog-structure.ts", "scripts/generate-meta.ts"]` and outputs `[".content-collections/**", "src/content/blog/**/meta.json"]` -- generated git-ignored files MUST be in turbo outputs or cached production builds ship a broken sidebar (catalogue #1) |

## Appendix: Tailwind 3 / fumadocs 14 path (legacy projects only)

For an existing project on Tailwind 3, use fumadocs-core/ui `14.6.1` + `@fumadocs/content-collections 1.1.5` + `@content-collections/core 0.10.0` (exact pins) and apply these substitutions to the templates:

| Templates (v16/TW4)                                                                                                   | v14/TW3 equivalent                                                                                                                                                                                                       |
| --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `@import 'fumadocs-ui/css/neutral.css'` + `@import 'fumadocs-ui/css/preset.css'` + `@source` directive in globals.css | `presets: [createPreset({ cssPrefix: "fd" })]` from `fumadocs-ui/tailwind-plugin` in tailwind.config.ts, plus the fumadocs-ui dist in content globs. NEVER hardcode the node_modules path (catalogue #12) -- resolve it: |

```ts
import path from "node:path";
const fumadocsUiDist = path
  .join(path.dirname(require.resolve("fumadocs-ui/tailwind-plugin")), "**/*.js")
  .split(path.sep)
  .join("/");
// content: [...yourGlobs, fumadocsUiDist]
```

| Templates (v16)                                                                                | v14 equivalent                                                          |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| OG URLs built manually (`/api/og/${slugs.join('/')}/og.png`)                                   | same code works, OR `createMetadataImage` from `fumadocs-core/server`   |
| `import type * as PageTree from 'fumadocs-core/page-tree'` (in `lib/utils/docs.ts`)            | `import type { PageTree } from 'fumadocs-core/server'`                  |
| `page.path` (relative to content dir) in the canonical resolver                                | `page.file.path` (relative to cwd) -- adjust `getCanonical` accordingly |
| `meta.path.split('/').slice(0, -1).join('/')` for the tab folder name (in `layout.config.tsx`) | `meta.file.dirname`                                                     |
| `--color-fd-*` bridge in `@theme`                                                              | `--fd-*` variables in `:root` (same mapping, different prefix)          |
| Tab colors as plain CSS vars                                                                   | identical                                                               |

Important: never downgrade Tailwind 4 to 3 just to run fumadocs 14. If the project is on Tailwind 4, use the templates as-is.
