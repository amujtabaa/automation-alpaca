/**
 * Meta.json Generator Script
 *
 * Generates individual meta.json files from the centralized blog-structure.ts
 *
 * Usage: pnpm generate:meta
 *
 * This script:
 * 1. Reads the blog-structure.ts master configuration
 * 2. Recursively generates meta.json files for each folder
 * 3. Only writes files if the folder exists (won't create folders)
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import { blogStructure, type BlogStructure, type MetaConfig } from '../src/content/blog/blog-structure.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const BLOG_DIR = path.resolve(__dirname, '../src/content/blog')

// Properties that belong in meta.json (not nested sections)
const META_PROPS = ['title', 'description', 'icon', 'root', 'defaultOpen', 'pages'] as const

interface GeneratorStats {
  generated: string[]
  skipped: string[]
}

function isMetaProp(key: string): key is (typeof META_PROPS)[number] {
  return META_PROPS.includes(key as (typeof META_PROPS)[number])
}

function extractMeta(structure: BlogStructure): MetaConfig {
  const meta: MetaConfig = {}

  for (const key of META_PROPS) {
    if (key in structure && structure[key] !== undefined) {
      ;(meta as Record<string, unknown>)[key] = structure[key]
    }
  }

  return meta
}

function extractNestedSections(structure: BlogStructure): Record<string, BlogStructure> {
  const nested: Record<string, BlogStructure> = {}

  for (const [key, value] of Object.entries(structure)) {
    if (!isMetaProp(key) && typeof value === 'object' && value !== null && !Array.isArray(value)) {
      nested[key] = value as BlogStructure
    }
  }

  return nested
}

function generateMetas(structure: BlogStructure, basePath: string, stats: GeneratorStats): void {
  const meta = extractMeta(structure)
  const nestedSections = extractNestedSections(structure)

  // Check if this folder exists
  if (!fs.existsSync(basePath)) {
    stats.skipped.push(basePath)
    console.log(`  Skipped (folder doesn't exist): ${path.relative(BLOG_DIR, basePath)}/`)
    return
  }

  // Write meta.json for this level
  const metaPath = path.join(basePath, 'meta.json')

  // Format the output - use simple format if only pages array at root
  let content: string
  if (Object.keys(meta).length === 1 && meta.pages) {
    // Simple array format for root level
    content = JSON.stringify({ pages: meta.pages }, null, 2) + '\n'
  } else {
    content = JSON.stringify(meta, null, 2) + '\n'
  }

  fs.writeFileSync(metaPath, content)
  stats.generated.push(metaPath)
  console.log(`  Generated: ${path.relative(BLOG_DIR, metaPath)}`)

  // Recursively process nested sections
  for (const [sectionName, sectionConfig] of Object.entries(nestedSections)) {
    const sectionPath = path.join(basePath, sectionName)
    generateMetas(sectionConfig, sectionPath, stats)
  }
}

function main(): void {
  console.log('\n📁 Generating meta.json files from blog-structure.ts\n')
  console.log(`  Base directory: ${BLOG_DIR}\n`)

  const stats: GeneratorStats = {
    generated: [],
    skipped: []
  }

  generateMetas(blogStructure, BLOG_DIR, stats)

  console.log('\n' + '='.repeat(50))
  console.log(`\n✅ Generated: ${stats.generated.length} meta.json files`)

  if (stats.skipped.length > 0) {
    console.log(`⚠️  Skipped: ${stats.skipped.length} folders (don't exist)`)
  }

  console.log('\n')
}

main()
