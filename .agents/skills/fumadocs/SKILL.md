---
name: fumadocs
description: "Fumadocs sidebar organization and content structure. Use when adding blog posts, fixing sidebar issues, or organizing documentation. Covers meta.json patterns, content collections, and common pitfalls."
---

# Fumadocs Content & Sidebar Organization

> **Setting up this blog in a NEW project?** Read `new-project-setup.md` -- a one-shot playbook backed by `templates/`, a complete anonymized working implementation (28+ files: content pipeline, docs layer, blog overlay, OG images, views system) ready to copy and brand.
> **Porting, upgrading, or repairing an existing install?** Also read `port-error-catalogue.md` (13 known failure modes from real-world deployments).

## Project Configuration

**Version**: Fumadocs 14.6.1 (fumadocs-core, fumadocs-ui)
**Integration**: @fumadocs/content-collections 1.1.5 + @content-collections/core 0.10.0
**Base URL**: `/blog/`

### Key Files

| File                                          | Purpose                                          |
| --------------------------------------------- | ------------------------------------------------ |
| `apps/web/src/content/blog/blog-structure.ts` | **SINGLE SOURCE OF TRUTH** for all navigation    |
| `apps/web/scripts/generate-meta.ts`           | Generates meta.json files from blog-structure.ts |
| `apps/web/content-collections.ts`             | Defines docs, metas, legal collections           |
| `apps/web/src/app/source.tsx`                 | Creates fumadocs loader with source config       |
| `apps/web/src/app/blog/layout.config.tsx`     | Sidebar customization and styling                |

> **IMPORTANT**: This project uses a **centralized meta.json system**. Individual `meta.json` files are auto-generated and git-ignored. See `centralized-meta-system.md` for full details.

---

## Adding New Posts: Step-by-Step (Centralized System)

### Step 1: Create MDX File

**Location**: `apps/web/src/content/blog/[section]/[subsection]/new-post.mdx`

**Required Frontmatter**:

```yaml
---
menu: "Short Title" # Sidebar display (~30 chars)
title: "Codex Feature" # SEO title & H1 (~80 chars, must include "Codex")
description: "Your description here" # Max 140 chars ("Codex Fast | " auto-prepended)
publishedAt: "2024-12-07" # Date in YYYY-MM-DD format
---
```

**With SEO Title Override** (optional):

```yaml
---
menu: "Short Title" # Sidebar
title: "Codex Feature" # H1 on page
seoTitle: "Shorter Search Title" # Use when title exceeds 60 chars
description: "Your description"
publishedAt: "2024-12-07"
---
```

**SEO Title Logic**:

1. `seoTitle` (if present) - used for all search engines (max 60 chars)
2. `title` - used as H1 and search title if under 60 chars
3. `menu` with breadcrumbs - fallback (rarely used)

> **Note**: "Codex Fast | " is auto-prepended to all descriptions.

See `frontmatter-template.md` in this skill directory for full documentation.

### Step 2: Update blog-structure.ts

**CRITICAL**: Edit `apps/web/src/content/blog/blog-structure.ts` - add the slug to the appropriate `pages` array:

```typescript
// In blog-structure.ts
mechanics: {
  title: "Mechanics",
  pages: [
    "existing-post",
    "new-post",         // <- ADD HERE (no .mdx extension!)
    "------",           // Separator (exactly 6 dashes)
    "another-post"
  ],
},
```

### Step 3: Generate meta.json files

```bash
pnpm generate:meta
```

This regenerates all `meta.json` files from the centralized config.

### Step 4: For New Subdirectories

1. Create the folder with your MDX files
2. Add section config to `blog-structure.ts`:

```typescript
guide: {
  pages: [..., "new-section"],  // Reference in parent's pages

  // Add nested config
  "new-section": {
    title: "New Section",
    description: "Section description",
    icon: "BookOpen",
    pages: ["first-post", "second-post"]
  }
}
```

3. Run `pnpm generate:meta`

---

## meta.json Schema Reference

```typescript
// Full object format
{
  title: string;           // Section display name (required for nested)
  description?: string;    // Tooltip/metadata
  pages?: string[];        // Array of slugs (files OR folders)
  icon?: string;           // Icon from @turbostarter/ui/Icons
  root?: boolean;          // Creates top-level tab
  defaultOpen?: boolean;   // Expand section by default
}

// Simple array format (root level only)
["page1", "page2", "subfolder"]
```

### Valid Icons

```
BookOpen, Wrench, Zap, LightBulb, Tools, Blog, Code, Terminal, Settings
```

---

## Directory Structure Pattern

```
src/content/blog/
├── meta.json                     # Root: {"pages": ["guide", "tools", "build"]}
├── guide/
│   ├── meta.json                 # {"title": "Guide", "root": true, "pages": [...]}
│   ├── index.mdx                 # Landing page for /blog/guide
│   ├── mechanics/
│   │   ├── meta.json             # {"title": "Mechanics", "pages": [...]}
│   │   └── post.mdx
│   └── development/
│       ├── meta.json
│       └── post.mdx
└── tools/
    ├── meta.json
    ├── index.mdx
    └── hooks/
        ├── meta.json
        └── hook-guide.mdx
```

**URL Pattern**: File path → URL

- `src/content/blog/guide/mechanics/post.mdx` → `/blog/guide/mechanics/post`

---

## Common Pitfalls & Fixes

### 0. Production Sidebar Structure Broken (Turbo Caching Issue)

**Symptoms**:

- Localhost shows correct tabs (Guide, Tools) at top level
- Production shows everything nested incorrectly - sections collapse into wrong hierarchy
- `root: true` tabs not rendering properly in production

**Root Cause**: Turbo caching issue. The `build:content` task wasn't including generated `meta.json` files in its outputs.

**The Problem**:

1. `meta.json` files are git-ignored (generated from `blog-structure.ts`)
2. Turbo cached `.content-collections/**` but NOT `src/content/blog/**/meta.json`
3. On cache hit, Turbo skipped `generate:meta` entirely
4. Without `meta.json` files, Fumadocs can't identify `root: true` tabs

**The Fix** (in `apps/web/turbo.json`):

```json
{
  "tasks": {
    "build:content": {
      "inputs": [
        "src/content/blog/blog-structure.ts",
        "scripts/generate-meta.ts"
      ],
      "outputs": [".content-collections/**", "src/content/blog/**/meta.json"]
    }
  }
}
```

**Deploy Fix (Vercel)**:

1. Commit the turbo.json change
2. Clear Vercel build cache: Project Settings → Git → Clear Build Cache
3. Redeploy

**Deploy Fix (EasyPanel/Coolify/Direct builds)**:
If your platform runs `pnpm build` directly (bypassing Turbo), update `apps/web/package.json`:

```json
"build": "pnpm build:content && next build",
```

This ensures `generate:meta` runs before every build regardless of how it's triggered.

**Prevention**: Always include generated files in turbo task outputs if they're git-ignored. For non-Turbo deployments, chain build:content into the main build script.

### 1. Page Not Appearing in Sidebar

**Cause**: Slug not in parent's meta.json or typo

**Check**:

```bash
# File exists?
ls apps/web/src/content/blog/guide/mechanics/new-post.mdx

# meta.json has slug?
cat apps/web/src/content/blog/guide/mechanics/meta.json | grep "new-post"
```

**Fix**: Add exact filename (without .mdx) to `pages` array

### 2. Wrong Page Order

**Cause**: Order determined by meta.json array, NOT alphabetical

**Fix**: Reorder items in `pages` array:

```json
{
  "pages": ["shows-first", "shows-second", "shows-third"]
}
```

### 3. Missing Subsection/Folder

**Cause**: Folder exists but no meta.json inside

**Fix**: Create `meta.json` in folder AND add folder to parent's pages:

```bash
# In new folder
echo '{"title": "New Section", "pages": ["first-post"]}' > meta.json

# In parent folder's meta.json, add "new-folder" to pages array
```

### 4. Separator Not Showing

**Cause**: Wrong format

**Fix**: Use exactly 6 dashes as a string:

```json
{
  "pages": ["post1", "------", "post2"]
}
```

### 5. Icon Not Rendering

**Cause**: Icon name doesn't exist in Icons collection

**Check valid icons**: Look at `@turbostarter/ui` Icons exports

### 6. Changes Not Reflecting

**Cause**: Content collections cache

**Fix**:

```bash
# Rebuild content
pnpm build:content

# Or restart dev server
# Ctrl+C then pnpm dev
```

### 7. 404 on New Page

**Causes**:

1. Frontmatter missing `title` or `heading`
2. File in wrong directory
3. Slug mismatch between filename and meta.json

---

## Troubleshooting Checklist

When sidebar items don't appear:

- [ ] Slug in `blog-structure.ts` matches filename (without .mdx)
- [ ] Ran `pnpm generate:meta` after editing blog-structure.ts
- [ ] Folder exists (generator won't create folders)
- [ ] No typos in slugs or file paths
- [ ] Frontmatter has `menu` and `title` (current contract; `heading` is the OLD field name)
- [ ] Separator is exactly `"------"` (6 dashes)
- [ ] Icon name exists in Icons collection
- [ ] For new folders: added to parent's `pages` array in blog-structure.ts

---

## Quick Commands

```bash
# Generate meta.json from centralized config
pnpm generate:meta

# Rebuild content collections (auto-runs generate:meta)
pnpm build:content

# View the master config
cat apps/web/src/content/blog/blog-structure.ts

# Validate frontmatter in MDX files
grep -r "^title:" apps/web/src/content/blog --include="*.mdx"

# Check generated meta.json files
find apps/web/src/content/blog -name "meta.json" -exec echo "=== {} ===" \; -exec cat {} \;
```

---

## Example: Adding a Post to Mechanics

```bash
# 1. Create MDX file
cat > apps/web/src/content/blog/guide/mechanics/my-new-post.mdx << 'EOF'
---
menu: "My New Post"
title: "My New Post: Complete Guide to This Feature"
description: "Learn everything about this feature in Codex."
publishedAt: "2024-12-07"
---

# Content here
EOF

# 2. Update blog-structure.ts - add "my-new-post" to mechanics.pages array
# Edit: apps/web/src/content/blog/blog-structure.ts
#
# mechanics: {
#   title: "Mechanics",
#   pages: [
#     "existing-posts",
#     "my-new-post",    // <- Add here
#   ],
# },

# 3. Generate and verify
pnpm generate:meta && pnpm dev
```

---

---

## Dynamic OG Image Customization

When setting up Fumadocs for a new blog/project, you need to customize the dynamic OG image generation.

### Key File

`apps/web/src/app/api/og/[...slug]/route.tsx`

### What to Customize

**1. Background Color** (Line ~119):

```tsx
<div
  tw="flex flex-col w-full h-full bg-[#272622] text-white"  // <- Change hex color
  style={{
    backgroundImage: `linear-gradient(to left bottom, rgba(255,255,255,0.08), transparent)`,
  }}
>
```

Match this to your theme's dark mode background from `packages/ui/src/styles/themes/[theme].css`:

- Look for `.dark[data-theme="..."] { --background: ... }`
- Convert HSL to hex

**2. Logo SVG** (Lines ~135-160):
Replace the logo section with your project's icon. The current implementation uses a circular background with an icon inside:

```tsx
<div
  tw="flex items-center justify-center rounded-full"
  style={{
    width: 65,
    height: 65,
    backgroundColor: "#C18653",  // <- Your brand color
  }}
>
  <svg ...>  // <- Your icon SVG paths
  </svg>
</div>
```

**Important**: `next/og` ImageResponse does NOT support:

- `foreignObject` SVGs (common in exported browser SVGs)
- External images/URLs in SVG
- Complex CSS

Use simple path-based SVGs only. Lucide icons work well.

**3. Cache Buster Version**:

```tsx
// In route.tsx
export const OG_DYNAMIC_VERSION = "v3"; // <- Increment after design changes
```

Also update in `lib/metadata.ts`:

```tsx
const OG_IMAGE_VERSION = "v3"; // <- Keep in sync
```

### Files That Reference OG Version

1. `apps/web/src/app/api/og/[...slug]/route.tsx` - Dynamic OG generation + version export
2. `apps/web/src/lib/metadata.ts` - Static OG image version
3. `apps/web/src/app/blog/[...slug]/page.tsx` - Imports and uses `OG_DYNAMIC_VERSION`

### Testing OG Images

```bash
# Start dev server
pnpm dev

# Visit dynamic OG image directly
# http://localhost:3000/api/og/blog/guide/getting-started/og.png
```

### Checklist for New Projects

- [ ] Update background color in `route.tsx` to match theme
- [ ] Replace logo SVG with project branding
- [ ] Update brand color for logo background
- [ ] Increment `OG_DYNAMIC_VERSION` in route.tsx
- [ ] Increment `OG_IMAGE_VERSION` in metadata.ts
- [ ] Replace static `opengraph-image.png` in `src/app/` if needed
- [ ] Test OG image rendering at `/api/og/[slug]/og.png`

---

## Content Collections Transform

The transform in `content-collections.ts` handles:

1. Git `lastModified` date extraction (falls back to file mtime)
2. MDX compilation with remark plugins
3. Mirror document resolution (for content reuse)

**Git Integration**: Files must be committed for accurate `lastModified`. Uncommitted files use file system timestamp.

---

## Sidebar Tab Customization

The tabs transform in `layout.config.tsx` colors each tab icon via `hsl(var(--<folder>-color))`, where `<folder>` is `meta.file.dirname` (the root content folder name). For this to work, BOTH must hold:

1. `globals.css` defines one HSL-triplet variable per root folder, light AND dark (current folders are guide/tools/models/build):

```css
:root { --guide-color: 17 80% 48%; --tools-color: ...; --models-color: ...; --build-color: ...; }
.dark { --guide-color: 17 85% 58%; ... }
```

2. The template literal in the transform uses REAL interpolation: `` `hsl(var(--${meta.file.dirname}-color))` `` -- not an escaped `$\{...\}`.

> Both conditions fail silently when broken (invalid CSS values render as nothing). After any folder rename or new root section, re-check the variables AND inspect a tab icon in devtools to confirm the computed color resolves. See `port-error-catalogue.md` #6. A correct working reference ships in `templates/`.
