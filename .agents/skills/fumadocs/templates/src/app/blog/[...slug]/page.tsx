import { DocsPage, DocsBody, DocsTitle, DocsDescription } from 'fumadocs-ui/page'
import { notFound } from 'next/navigation'
import path from 'path'

import { OG_DYNAMIC_VERSION } from '@/app/api/og/[...slug]/route'
import { docs } from '@/app/source'
import { BlogCategory } from '@/components/blog/blog-category'
import { Mdx } from '@/components/mdx/mdx'
import { getMetadata, publicUrl, SITE_NAME } from '@/lib/metadata'
import { generateArticleSchema, generateBreadcrumbSchema } from '@/lib/schema'

import type { Metadata } from 'next'

interface Param {
  slug: string[]
}

// fumadocs-core v16 removed createMetadataImage - build the OG image URL directly.
// The /api/og route serves /api/og/<...slugs>/og.png
const getOgImageUrl = (slugs: string[]) => `/api/og/${slugs.join('/')}/og.png`

export default async function Page({ params }: { params: Promise<Param> }) {
  const page = docs.getPage((await params).slug)

  if (!page) notFound()

  const ogImageUrl = getOgImageUrl(page.slugs)

  // Handle lastModified which might be Date, string, or undefined
  const getDateString = (date: Date | string | undefined): string => {
    if (!date) return new Date().toISOString()
    if (typeof date === 'string') return date
    return date.toISOString()
  }

  const articleSchema = generateArticleSchema({
    headline: page.data.seoTitle || page.data.heading,
    description: page.data.description || '',
    image: `${publicUrl}${ogImageUrl}?${OG_DYNAMIC_VERSION}`,
    datePublished: getDateString(page.data.publishedAt || page.data.lastModified),
    dateModified: getDateString(page.data.lastModified),
    author: {
      name: 'Your Name'
    },
    publisher: {
      name: SITE_NAME,
      logo: `${publicUrl}/apple-icon.png`
    },
    url: `${publicUrl}${page.url}`
  })

  // Breadcrumb schema for navigation SEO
  const breadcrumbSchema = generateBreadcrumbSchema({
    items: [
      { name: 'Home', url: publicUrl },
      { name: 'Blog', url: `${publicUrl}/blog` },
      {
        name: page.data.heading,
        url: `${publicUrl}${page.url}`
      }
    ]
  })

  return (
    <>
      <script
        type='application/ld+json'
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
      />
      <script
        type='application/ld+json'
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />
      <DocsPage
        toc={page.data.toc}
        lastUpdate={page.data.lastModified}
        full={page.data.full}
        tableOfContent={{
          style: 'clerk',
          single: false
        }}
      >
        <DocsTitle className='-my-1 text-3xl font-medium tracking-tight lg:my-0'>
          {page.data.heading}
        </DocsTitle>
        <DocsDescription className='-mt-3 mb-4 text-base'>{page.data.description}</DocsDescription>
        <DocsBody>
          <Mdx body={page.data.body} />

          {page.data.index ? <BlogCategory page={page} className='mt-8' /> : null}
        </DocsBody>
      </DocsPage>
    </>
  )
}

export async function generateMetadata({ params }: { params: Promise<Param> }): Promise<Metadata> {
  const page = docs.getPage((await params).slug)

  if (!page) notFound()

  // Add version query param for cache busting
  const image = {
    url: `${getOgImageUrl(page.slugs)}?${OG_DYNAMIC_VERSION}`,
    width: 1200,
    height: 630
  }

  const canonical = page.data.mirror
    ? getCanonical(page.path, page.data.mirror)
    : `${publicUrl}${page.url}`

  // SEO title priority: seoTitle > heading (direct, no breadcrumbs) > menu
  const seoTitle = page.data.seoTitle || page.data.heading || page.data.menu

  // Prepend brand to description for SEO visibility (moved from title suffix)
  const seoDescription = page.data.description
    ? `Acme | ${page.data.description}`
    : undefined

  return {
    ...getMetadata({
      title: seoTitle,
      description: seoDescription,
      image,
      url: page.url,
      type: 'article',
      ...(canonical && {
        canonical
      })
    }),
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true
      }
    }
  }
}

const getCanonical = (file: string, mirror: string) => {
  // v16: page.path is relative to the content directory (e.g. "guide/post.mdx")
  const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(file), mirror))

  return docs.getPages().find(p => p.path === resolved)?.url
}

export function generateStaticParams(): Param[] {
  return docs.generateParams()
}
