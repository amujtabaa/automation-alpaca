import { defineCollection, defineConfig } from '@content-collections/core'
import { transformMDX } from '@fumadocs/content-collections/configuration'
import { z } from 'zod'
import { remarkImage } from 'fumadocs-core/mdx-plugins'

import { getLastModifiedAt, getMirrorDoc } from './src/lib/utils/content'

const docs = defineCollection({
  name: 'docs',
  directory: 'src/content/blog',
  include: '**/*.mdx',
  schema: z.object({
    menu: z.string(), // Short name for sidebar navigation (max 30 chars)
    title: z.string(), // H1 on page, also used as search title if no seoTitle (max 80 chars)
    seoTitle: z.string().optional(), // Override for search engines when title exceeds 60 chars
    description: z.string().optional(), // Meta description (max 140 chars, "Acme | " auto-prepended at render)
    icon: z.string().optional(),
    full: z.boolean().optional(),
    _openapi: z.record(z.string(), z.any()).optional(),
    index: z.boolean().optional().default(false),
    mirror: z.string().optional(),
    publishedAt: z.string().optional(), // Publication date in YYYY-MM-DD format
    views: z.number().optional() // Estimated view count for popularity sorting
  }),
  transform: async (doc, context) => {
    const lastModified = await context.cache(doc._meta.filePath, getLastModifiedAt)

    const content = doc.mirror
      ? getMirrorDoc(context.collection.directory, doc._meta.filePath, doc.mirror).content
      : doc.content

    // Transform doc with 'title' field mapped for Fumadocs navigation
    // Fumadocs expects 'title' for sidebar - we use 'menu' in frontmatter
    const mdx = await transformMDX(
      {
        ...doc,
        title: doc.menu, // Map menu to title for Fumadocs navigation
        content
      },
      context,
      { remarkPlugins: [remarkImage] }
    )

    return {
      ...mdx,
      // Keep title from transformMDX (mapped from menu) for Fumadocs sidebar
      // Add separate fields for page display
      menu: doc.menu, // Original menu field for reference
      heading: doc.title, // H1 on page (NOT 'title' - that's used by Fumadocs sidebar)
      seoTitle: doc.seoTitle, // Optional search engine title override
      views: doc.views,
      lastModified
    }
  }
})

// Object-only schema. blog-structure.ts always generates objects, and
// content-collections requires a serializable object output.
const metaSchema = z.object({
  title: z.string().optional(),
  pages: z.array(z.string()).optional(),
  description: z.string().optional(),
  root: z.boolean().optional(),
  defaultOpen: z.boolean().optional(),
  icon: z.string().optional()
})

const metas = defineCollection({
  name: 'meta',
  directory: 'src/content/blog',
  include: '**/meta.json',
  parser: 'json',
  schema: metaSchema
})

export default defineConfig({
  collections: [docs, metas]
})
