/**
 * SINGLE SOURCE OF TRUTH FOR BLOG NAVIGATION
 *
 * This file controls all meta.json files in the blog directory.
 * Run `pnpm generate:meta` to regenerate individual meta.json files.
 * meta.json files are git-ignored (add `src/content/blog/**\/meta.json` to .gitignore).
 *
 * Structure:
 * - Top-level keys that match MetaConfig properties (title, description, icon, root, defaultOpen, pages)
 *   become part of that folder's meta.json
 * - Other top-level keys are treated as nested folder configurations
 * - `root: true` turns a section into a sidebar TAB (with colored icon, see globals-blog.css)
 * - A separator entry is exactly "------" (6 dashes)
 *
 * MDX Frontmatter Fields (in each .mdx file):
 * - menu: Controls SIDEBAR name only (keep short, max 30 chars)
 * - title: Controls H1 on page + SEO title (longer, SEO-optimized, max 80 chars)
 * - seoTitle: Optional override for search engines when title exceeds 60 chars
 * - description: Controls meta description for SEO (max 140 chars - the brand
 *   prefix "Acme | " is auto-prepended at render, see blog/[...slug]/page.tsx)
 * - publishedAt: "YYYY-MM-DD"
 * - views: Optional number for popularity sorting (see scripts/views-pull.ts)
 * - index: true on a section's index.mdx renders the category card grid
 */

export interface MetaConfig {
  title?: string;
  description?: string;
  icon?: string;
  root?: boolean;
  defaultOpen?: boolean;
  pages?: string[];
}

export interface BlogStructure extends MetaConfig {
  [key: string]:
    | MetaConfig
    | BlogStructure
    | string
    | string[]
    | boolean
    | undefined;
}

// TODO: replace the example sections below with your own.
// Each top-level key needs a matching folder in src/content/blog/.
export const blogStructure: BlogStructure = {
  // Root level - controls src/content/blog/meta.json
  pages: ["guide", "tutorials", "comparisons"],

  guide: {
    title: "Guide",
    description: "Learn everything about Acme",
    icon: "BookOpen", // lucide-react icon name (resolved in src/app/source.tsx)
    root: true, // sidebar tab
    pages: [
      "index",
      "getting-started",
      "------", // separator
      "advanced-usage",
    ],
  },

  tutorials: {
    title: "Tutorials",
    description: "Step-by-step walkthroughs",
    icon: "GraduationCap",
    root: true,
    pages: ["index", "first-tutorial"],
  },

  comparisons: {
    title: "Comparisons",
    description: "How Acme stacks up",
    icon: "Scale",
    root: true,
    pages: ["index"],
  },
};
