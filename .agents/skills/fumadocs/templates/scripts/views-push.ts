/**
 * Views Push Script
 *
 * Reads the edited views-master.yaml and updates MDX frontmatter.
 * Run: pnpm views:push
 *
 * Only updates the views field. Does not touch other frontmatter.
 */

import fs from "fs";
import path from "path";
import yaml from "yaml";
import matter from "gray-matter";

const BLOG_DIR = path.join(process.cwd(), "src/content/blog");
const MASTER_FILE = path.join(process.cwd(), "scripts/views-master.yaml");

interface MasterPost {
  slug: string;
  menu?: string;
  views: number;
}

interface MasterData {
  posts: MasterPost[];
}

interface UpdateResult {
  slug: string;
  oldViews: number;
  newViews: number;
  changed: boolean;
  error?: string;
}

function updateMdxFile(post: MasterPost): UpdateResult {
  const filePath = path.join(BLOG_DIR, `${post.slug}.mdx`);
  const result: UpdateResult = {
    slug: post.slug,
    oldViews: 0,
    newViews: post.views,
    changed: false,
  };

  if (!fs.existsSync(filePath)) {
    result.error = "File not found";
    return result;
  }

  const content = fs.readFileSync(filePath, "utf-8");
  const { data: frontmatter, content: body } = matter(content);

  result.oldViews = frontmatter.views ?? 0;

  if (frontmatter.views === post.views) {
    return result;
  }

  frontmatter.views = post.views;
  result.changed = true;

  // Reconstruct the file preserving format
  let newFrontmatter = "---\n";
  for (const [key, value] of Object.entries(frontmatter)) {
    if (typeof value === "string") {
      newFrontmatter += `${key}: "${value.replace(/"/g, '\\"')}"\n`;
    } else if (typeof value === "boolean") {
      newFrontmatter += `${key}: ${value}\n`;
    } else if (typeof value === "number") {
      newFrontmatter += `${key}: ${value}\n`;
    } else {
      newFrontmatter += `${key}: ${value}\n`;
    }
  }
  newFrontmatter += "---\n";
  const newContent = newFrontmatter + body;
  fs.writeFileSync(filePath, newContent);

  return result;
}

// Main
console.log("\n📤 Views Push - Updating MDX files from master...\n");

if (!fs.existsSync(MASTER_FILE)) {
  console.error(`Master file not found: ${MASTER_FILE}`);
  console.error("   Run 'pnpm views:pull' first to generate it.");
  process.exit(1);
}

const masterContent = fs.readFileSync(MASTER_FILE, "utf-8");
const masterData: MasterData = yaml.parse(masterContent);

if (!masterData.posts || !Array.isArray(masterData.posts)) {
  console.error("Invalid master file format. Expected 'posts' array.");
  process.exit(1);
}

let updatedCount = 0;
let errorCount = 0;
const updates: UpdateResult[] = [];

for (const post of masterData.posts) {
  if (!post.slug) continue;

  const result = updateMdxFile(post);
  updates.push(result);

  if (result.error) {
    errorCount++;
  } else if (result.changed) {
    updatedCount++;
  }
}

// Report
console.log("Results:");
console.log("-".repeat(60));

const changedPosts = updates.filter((u) => u.changed);
const errorPosts = updates.filter((u) => u.error);

if (changedPosts.length > 0) {
  console.log("\nUpdated posts:");
  for (const update of changedPosts) {
    const arrow =
      update.newViews > update.oldViews
        ? `${update.oldViews} -> ${update.newViews}`
        : `${update.oldViews} -> ${update.newViews}`;
    console.log(`  ${update.slug}: ${arrow}`);
  }
}

if (errorPosts.length > 0) {
  console.log("\nErrors:");
  for (const update of errorPosts) {
    console.log(`  ${update.slug}: ${update.error}`);
  }
}

if (changedPosts.length === 0 && errorPosts.length === 0) {
  console.log("\n  No changes detected.");
}

console.log("\n" + "-".repeat(60));
console.log(`\nSummary:`);
console.log(`  Updated: ${updatedCount}`);
console.log(`  Unchanged: ${updates.length - updatedCount - errorCount}`);
console.log(`  Errors: ${errorCount}`);
console.log("");

if (updatedCount > 0) {
  console.log("Next steps:");
  console.log("  1. Review changes: git diff");
  console.log("  2. Commit if satisfied");
  console.log("");
}
