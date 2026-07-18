# Centralized Meta.json System

This project uses a **custom centralized meta.json system** that generates all individual `meta.json` files from a single source of truth.

## Architecture

```
blog-structure.ts  →  pnpm generate:meta  →  Individual meta.json files
   (source)              (generator)            (git-ignored, generated)
```

## Key Files

| File | Purpose |
|------|---------|
| `apps/web/src/content/blog/blog-structure.ts` | Single source of truth for all navigation |
| `apps/web/scripts/generate-meta.ts` | Generator script |
| `apps/web/src/content/blog/**/meta.json` | Generated files (git-ignored) |

## Why This Exists

Standard Fumadocs requires a `meta.json` in every folder. This becomes tedious when:
- Adding new sections requires editing multiple files
- Reordering navigation means touching many folders
- Easy to have stale or inconsistent meta.json files

The centralized system solves this by:
- Single file to edit for all navigation changes
- Auto-generates all meta.json files at build time
- meta.json files are git-ignored (not version controlled)
- Type-safe configuration with TypeScript

---

## Usage

### Adding a New Post

1. Create MDX file in the appropriate folder
2. Edit `blog-structure.ts` - add slug to the `pages` array
3. Run `pnpm generate:meta` (or it runs automatically on build)

```typescript
// In blog-structure.ts
mechanics: {
  title: "Mechanics",
  pages: [
    "existing-post",
    "new-post",        // <- Add here
  ],
},
```

### Adding a New Section

1. Create the folder with your MDX files
2. Add section config to `blog-structure.ts`:

```typescript
// In blog-structure.ts
guide: {
  pages: [..., "new-section"],  // Reference in parent

  // Add nested config
  "new-section": {
    title: "New Section",
    description: "Optional description",
    icon: "BookOpen",           // Optional icon
    pages: ["post-1", "post-2"]
  }
}
```

3. Run `pnpm generate:meta`

### Reordering Navigation

Just reorder items in the `pages` array:

```typescript
pages: [
  "shows-first",
  "------",          // Separator
  "shows-second",
  "shows-third",
]
```

---

## blog-structure.ts Schema

```typescript
interface MetaConfig {
  title?: string;        // Section display name
  description?: string;  // Tooltip/metadata
  icon?: string;         // Icon from @turbostarter/ui/Icons
  root?: boolean;        // Creates top-level tab
  defaultOpen?: boolean; // Expand section by default
  pages?: string[];      // Array of slugs (files OR folders)
}

interface BlogStructure extends MetaConfig {
  [key: string]: MetaConfig | BlogStructure | ...;  // Nested sections
}
```

### Example Structure

```typescript
export const blogStructure: BlogStructure = {
  // Root level
  pages: ["guide", "tools", "build"],

  // Guide section
  guide: {
    title: "Guide",
    description: "Learn everything about Claude",
    icon: "BookOpen",
    root: true,
    pages: ["index", "getting-started", "------", "mechanics", "development"],

    // Nested subsection
    mechanics: {
      title: "Mechanics",
      pages: ["claude-skills-guide", "context-management"]
    },

    development: {
      title: "Development",
      pages: ["git-integration", "todo-workflows"]
    }
  },

  // Tools section
  tools: {
    title: "Tools",
    icon: "Wrench",
    root: true,
    pages: ["index", "hooks"],

    hooks: {
      title: "Hooks",
      icon: "Zap",
      pages: ["skill-activation-hook"]
    }
  }
};
```

---

## Scripts

```bash
# Generate meta.json files from blog-structure.ts
pnpm generate:meta

# Build content (auto-runs generate:meta first)
pnpm build:content

# Full build (includes meta generation)
pnpm build
```

---

## How the Generator Works

The `generate-meta.ts` script:

1. Imports `blogStructure` from `blog-structure.ts`
2. Recursively walks the structure
3. For each level:
   - Extracts meta properties (`title`, `pages`, `icon`, etc.)
   - Writes `meta.json` to the corresponding folder
   - Processes nested sections recursively
4. Only writes if the folder exists (won't create folders)

---

## Troubleshooting

### Production sidebar broken (Turbo caching)

**Symptoms**: Localhost works, production has broken hierarchy/tabs.

**Cause**: Turbo cache hits skip `generate:meta`, and meta.json files aren't restored because they weren't in task outputs.

**Fix (Turbo/Vercel)**: Ensure `apps/web/turbo.json` includes:
```json
{
  "build:content": {
    "inputs": ["src/content/blog/blog-structure.ts", "scripts/generate-meta.ts"],
    "outputs": [".content-collections/**", "src/content/blog/**/meta.json"]
  }
}
```

**Fix (EasyPanel/Coolify/Direct builds)**: Update `apps/web/package.json`:
```json
"build": "pnpm build:content && next build",
```

This ensures meta.json generation runs before every build, regardless of deployment platform.

### Changes not reflecting

Run `pnpm generate:meta` after editing `blog-structure.ts`, then refresh.

### Folder skipped

The generator only writes to existing folders. Create the folder first, then run the generator.

### Type errors in blog-structure.ts

Ensure nested keys don't conflict with MetaConfig properties (`title`, `description`, `icon`, `root`, `defaultOpen`, `pages`).

### Git showing meta.json changes

meta.json files are git-ignored. If they appear in git status, they may have been tracked before. Run:

```bash
git rm --cached apps/web/src/content/blog/**/meta.json
```

---

## Reverting to Standard Fumadocs

If you need to stop using this system:

1. Run `pnpm generate:meta` one final time
2. Remove meta.json entries from `.gitignore`
3. Add all meta.json files to git: `git add apps/web/src/content/blog/**/meta.json`
4. Remove `generate:meta` from package.json scripts
5. Edit meta.json files directly going forward
