import { docs } from '@/app/source'
import type { BlogFilterParams } from '@/lib/blog-schema'

export type BlogCardData = {
  slug: string
  name: string
  tagline?: string
  description?: string
  publishedAt?: Date
  coreSection: string | null
  subsection: string | null
  icon?: string | null
  views?: number
}

/**
 * Extract two-level categorization from page path
 */
function extractCategories(slugs: string[]): { coreSection: string | null; subsection: string | null } {
  if (slugs.length === 0) {
    return { coreSection: null, subsection: null }
  }

  // Core section is always the first slug (guide, build, etc.)
  const coreSection = capitalize(slugs[0]!)

  // Subsection is the second slug if it exists (mechanics, agents, etc.)
  const subsection = slugs.length > 2 ? capitalize(slugs[1]!) : null

  return { coreSection, subsection }
}

/**
 * Capitalize folder names properly
 */
function capitalize(str: string): string {
  return str
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/**
 * Get all unique sections (core sections) from the docs
 */
export function getUniqueSections(): string[] {
  const allPages = docs.getPages()
  const sections = new Set<string>()

  allPages.forEach(page => {
    const { coreSection } = extractCategories(page.slugs)
    if (coreSection) {
      sections.add(coreSection)
    }
  })

  return Array.from(sections).sort()
}

/**
 * Get all unique categories (subsections) from the docs
 */
export function getUniqueCategories(section?: string): string[] {
  const allPages = docs.getPages()
  const categories = new Set<string>()

  allPages.forEach(page => {
    const { coreSection, subsection } = extractCategories(page.slugs)

    // If section filter is provided, only include categories from that section
    if (section && coreSection?.toLowerCase() !== section.toLowerCase()) {
      return
    }

    if (subsection) {
      categories.add(subsection)
    }
  })

  return Array.from(categories).sort()
}

/**
 * Search and filter blog pages
 */
export async function searchBlogs(params: BlogFilterParams) {
  const { q, sort, page, perPage, section, category } = params

  // Get all pages from fumadocs
  const allPages = docs.getPages()

  // Transform to BlogCardData format
  let blogsData: BlogCardData[] = allPages.map(page => {
    const { coreSection, subsection } = extractCategories(page.slugs)
    return {
      slug: page.slugs.join('/'),
      name: page.data.title,
      tagline: page.data.description,
      description: page.data.description,
      publishedAt: page.data.publishedAt
        ? new Date(page.data.publishedAt)
        : page.data.lastModified
          ? new Date(page.data.lastModified)
          : undefined,
      coreSection,
      subsection,
      icon: page.data.icon || null,
      views: page.data.views ?? 0
    }
  })

  // Filter by search query
  if (q && q.trim() !== '') {
    const query = q.toLowerCase()
    blogsData = blogsData.filter(
      blog =>
        blog.name.toLowerCase().includes(query) ||
        blog.tagline?.toLowerCase().includes(query) ||
        blog.description?.toLowerCase().includes(query)
    )
  }

  // Filter by section
  if (section && section.trim() !== '') {
    blogsData = blogsData.filter(blog => blog.coreSection?.toLowerCase() === section.toLowerCase())
  }

  // Filter by category
  if (category && category.trim() !== '') {
    blogsData = blogsData.filter(blog => blog.subsection?.toLowerCase() === category.toLowerCase())
  }

  // Sort
  if (sort) {
    const [field, direction] = sort.split('.')

    blogsData.sort((a, b) => {
      let aVal: unknown = a[field as keyof BlogCardData]
      let bVal: unknown = b[field as keyof BlogCardData]

      // Handle name sorting (string)
      if (field === 'name') {
        aVal = (aVal as string)?.toLowerCase() || ''
        bVal = (bVal as string)?.toLowerCase() || ''
        const comparison = (aVal as string).localeCompare(bVal as string)
        return direction === 'asc' ? comparison : -comparison
      }

      // Handle date sorting
      if (field === 'publishedAt') {
        const aTime = aVal ? (aVal as Date).getTime() : 0
        const bTime = bVal ? (bVal as Date).getTime() : 0
        return direction === 'asc' ? aTime - bTime : bTime - aTime
      }

      // Handle views sorting (number)
      if (field === 'views') {
        const aViews = (aVal as number) ?? 0
        const bViews = (bVal as number) ?? 0
        return direction === 'asc' ? aViews - bViews : bViews - aViews
      }

      return 0
    })
  }

  // Calculate pagination
  const total = blogsData.length
  const start = (page - 1) * perPage
  const end = start + perPage
  const paginatedBlogs = blogsData.slice(start, end)

  return {
    blogs: paginatedBlogs,
    total,
    page,
    perPage
  }
}
