# Blog Setup Error Catalogue

> Every failure mode observed in real-world deployments and ports of this blog architecture. Format: symptom -> root cause -> fix -> prevention. Read alongside `new-project-setup.md`. Numbers are referenced from the playbook.

## 1. Production sidebar broken, localhost fine (turbo cache)

- **Symptom**: root tabs collapse / wrong hierarchy ONLY in production; localhost is correct.
- **Root cause**: in a turbo monorepo, the `build:content` task outputs didn't include the git-ignored `src/content/blog/**/meta.json`; on a cache hit turbo skipped `generate:meta` entirely and the build shipped without navigation files.
- **Fix**: add the meta.json glob to the turbo task outputs; clear the build cache; redeploy.
- **Prevention**: generated git-ignored files ALWAYS go in turbo task outputs. Non-turbo deploys are safe as long as `build` chains `build:content`.

## 2. Fork-and-forget staleness (the #1 killer)

- **Symptom**: a copied blog "works" but quietly lacks months of refinements: old SEO title strategy, no views system, no robots hardening, OG images overlapping on long titles.
- **Root cause**: one-time copy with no manifest and no flow-down; the original keeps evolving.
- **Fix**: diff the copy against the playbook's file manifest, port feature by feature, preserving the copy's intentional branding.
- **Prevention**: when improving any blog instance, record the improvement in this skill; periodically re-diff other instances against the manifest.

## 3. Version drift via caret ranges

- **Symptom**: a copy behaves differently or APIs are missing; in one real case a copy silently drifted TWO major versions of fumadocs (and one major of content-collections) from the original via `^` ranges.
- **Root cause**: caret ranges in package.json let installs float across breaking releases.
- **Fix**: pin exact versions (the matrix in `templates/package-additions.jsonc`).
- **Prevention**: exact pins, no carets, for the fumadocs + content-collections suite.

## 4. Fumadocs v14 -> v16 API removals (when migrating an old install forward)

All observed and build-verified during a real migration:

- `fumadocs-core/server` module is GONE in v16: `createMetadataImage` removed (build OG URLs manually: `/api/og/${slugs.join('/')}/og.png`); `PageTree` types now `import type * as PageTree from 'fumadocs-core/page-tree'`.
- `page.file.path` -> `page.path`, now relative to the CONTENT directory (mirror/canonical resolution must change).
- `meta.file.dirname` -> derive from `meta.path` (`meta.path.split('/').slice(0, -1).join('/')`).
- Styling: the TW3 `createPreset` tailwind-plugin -> `@import 'fumadocs-ui/css/neutral.css'` (TW4). NEVER downgrade Tailwind 4 to 3 just to run fumadocs 14; migrate the fumadocs code forward instead.
- content-collections 0.13 deprecation warning about the implicit `content` property: do NOT add `content` to the docs zod schema to silence it (that forces `content` into frontmatter). The warning is harmless.

## 5. Missing subsystems (nothing fails, you just lose them)

- **Symptom**: builds green, but no dynamic OG images / no views scripts / no JSON-LD / no canonical / no robots block. Real ports have been missing ALL of these simultaneously.
- **Root cause**: none of these break compilation, so partial copies omit them invisibly.
- **Fix/Prevention**: the verification checklist in the playbook checks each one explicitly (view page source; hit the OG URL directly).

## 6. Inert sidebar tab colors

- **Symptom**: tab icons render uncolored, with no error anywhere.
- **Two stacked root causes** (both seen in production):
  1. The template literal in the tabs transform was ESCAPED -- `` `hsl(var(--$\{...\}-color))` `` renders the literal text `${...}` instead of interpolating.
  2. The CSS variables were named after OLD folder names after a content reorganization -- the transform looked for `--<current-folder>-color`, which was never defined.
- **Fix**: real interpolation + one `--<folder>-color` (HSL triplet, light + dark) per CURRENT root folder.
- **Prevention**: after setup, inspect a tab icon in devtools and confirm the computed color actually resolves. Invalid CSS values fail silently.

## 7. CRLF line endings

- **Symptom**: collaborators' git diffs show every line changed; `bad interpreter` errors on Linux for scripts.
- **Root cause**: files copied on Windows without normalization.
- **Fix**: dos2unix the copied tree; `.gitattributes` with `* text=auto eol=lf`.
- **Prevention**: verification checklist includes a line-ending check.

## 8. Wholesale-copy clobbers intentional adaptations

- **Symptom**: after "syncing" a shared file from a reference implementation, a project-specific behavior silently breaks. Real case: overwriting the blog data layer erased a custom rule that mapped root-level posts into a default section.
- **Root cause**: intentional adaptations live INSIDE files that look copy-verbatim.
- **Fix/Prevention**: before overwriting any file in an existing install, diff the local version against the template and classify every difference: stale vs intentional. Keep a written registry of intentional differences.

## 9. Frontmatter contract drift (title/heading vs menu/title/seoTitle)

- **Symptom**: long SEO titles showing in the sidebar, or H1s showing short menu names; seoTitle ignored.
- **Root cause**: an older contract used `title` = sidebar and `heading` = H1/SEO. The current contract is `menu` (sidebar), `title` (H1 + SEO), `seoTitle` (optional override).
- **Fix**: migrate frontmatter (first `^title:` -> `menu:`, THEN first `^heading:` -> `title:` per file -- order matters or the fields collide), together with the content-collections schema/transform and the post page.
- **Prevention**: schema, transform, post page, and posts are one atomic contract -- never change one without the others.

## 10. Branding/naming leftovers

- **Symptom**: component names from the original brand surviving in a different product for months (works fine, reads wrong, confuses future maintenance), or original-brand strings in comments and aria-labels.
- **Root cause**: copy-then-rename discipline breaks down for identifiers that still compile.
- **Prevention**: at setup time, grep the copied tree for the template placeholder brand (case-insensitive) and resolve every hit. The playbook's branding step ends with exactly this search.

## 11. AI formatter hooks mangling cross-repo writes (tooling)

- **Symptom**: when an AI agent writes TypeScript into a DIFFERENT repository than the one it runs in, generics can get stripped by a post-write formatter hook (`Promise<Param>` -> `Promise`, `WithContext<Organization>` -> `WithContext`), causing confusing type errors.
- **Root cause**: the hook formats files in external repos with a mismatched parser config.
- **Workaround**: write cross-repo .ts/.tsx via shell heredoc/perl instead of the Write/Edit tools, or scope the hook to skip paths outside the project.

## 12. Fumadocs CSS purged in production only (broken sidebar/TOC soup) -- Tailwind 3 installs

- **Symptom**: the post page sidebar, TOC popover, and nav render stacked and overlapping at the top-left with no positioning -- ONLY in production; localhost is perfect.
- **Diagnosis**: count `fd-` occurrences in the served CSS vs a local build (`grep -o "fd-" <file>.css | wc -l`). Healthy is in the hundreds; purged is under ~100 (only your own bridge variables survive).
- **Root cause**: with fumadocs-ui 14.x, the component classes are generated from the Tailwind content glob over the fumadocs-ui dist folder. A hardcoded `"../../node_modules/fumadocs-ui/dist/**/*.js"` path can exist on your machine (hoisted layout) but NOT in the build container (pnpm isolated layout) -- the glob matches zero files and Tailwind purges every fd class.
- **Fix**: resolve the real install location instead of hardcoding (snippet in the playbook appendix). It cannot miss: if the `createPreset` import works at build time, `require.resolve` of the same specifier gives the true path.
- **Prevention**: never hardcode node_modules paths in Tailwind content globs. The modern path (fumadocs v15+/TW4, used by the templates) is immune -- CSS is imported directly.

## 13. SEO title strategy is a deliberate decision, not a default

- The shipped best practice: `SITE_NAME_TEMPLATE = "%s"` (no site-name suffix), brand moved into a description prefix (`"<Brand> | <description>"`), `seoTitle` override for >60-char titles.
- Adopting this on a site that is ALREADY LIVE changes its titles in search results while Google re-crawls. That is usually a CTR improvement, but it is a visible change -- make it consciously, not as a side effect of an upgrade.
