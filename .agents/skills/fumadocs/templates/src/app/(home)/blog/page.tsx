import type { Metadata } from 'next'
import type { SearchParams } from 'nuqs'

import { BlogHeading } from '@/components/blog/blog-heading'
import { BlogQuery } from '@/components/blog/blog-query'
import { getMetadata, publicUrl, SITE_NAME } from '@/lib/metadata'
import { generateOrganizationSchema, generateBlogSchema } from '@/lib/schema'

export const revalidate = 7200

const BLOG_TITLE = 'Guides, Tutorials & Product Insights' // TODO: your blog's H1/SEO title
const BLOG_DESCRIPTION = 'Everything you need to get the most out of Acme.' // TODO: your blog description

export async function generateMetadata(): Promise<Metadata> {
  return getMetadata({
    title: BLOG_TITLE,
    description: BLOG_DESCRIPTION,
    canonical: `${publicUrl}/blog`
  })
}

const BlogPage = async ({ searchParams }: { searchParams: Promise<SearchParams> }) => {
  // Organization schema for SEO
  const organizationSchema = generateOrganizationSchema({
    name: SITE_NAME,
    url: publicUrl,
    logo: `${publicUrl}/apple-icon.png`,
    description: BLOG_DESCRIPTION,
    sameAs: ['https://x.com/yourhandle'] // TODO: your social profiles
  })

  // Blog schema for blog listing page
  const blogSchema = generateBlogSchema({
    name: BLOG_TITLE,
    description: BLOG_DESCRIPTION,
    url: `${publicUrl}/blog`,
    publisher: {
      name: SITE_NAME,
      logo: `${publicUrl}/apple-icon.png`
    }
  })

  return (
    <>
      <script type='application/ld+json' dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }} />
      <script type='application/ld+json' dangerouslySetInnerHTML={{ __html: JSON.stringify(blogSchema) }} />
      <main className='container mx-auto max-w-7xl space-y-12 px-4 py-12'>
        {/* Switching Text Heading */}
        <div className='space-y-4 text-center'>
          <BlogHeading />
          <p className='text-muted-foreground mx-auto max-w-2xl md:text-lg'>
            Everything you need to get the most
            <br />
            out of Acme
          </p>
        </div>

        {/* Blog Posts with Search/Filter */}
        <BlogQuery searchParams={searchParams} />
      </main>
    </>
  )
}

export default BlogPage
