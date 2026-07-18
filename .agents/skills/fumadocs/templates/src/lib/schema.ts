import type { Organization, Article, Blog, BreadcrumbList, WithContext } from 'schema-dts'

/**
 * Generate Organization schema for brand identity
 * Used on homepage for company/brand information
 */
export function generateOrganizationSchema(data: {
  name: string
  url: string
  logo: string
  description: string
  sameAs?: string[] // Social media profiles
}): WithContext<Organization> {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: data.name,
    url: data.url,
    logo: data.logo,
    description: data.description,
    ...(data.sameAs && { sameAs: data.sameAs })
  }
}

/**
 * Generate Article schema for blog posts
 * Used on individual blog post pages
 */
export function generateArticleSchema(data: {
  headline: string
  description: string
  image: string
  datePublished: string
  dateModified?: string
  author: {
    name: string
    url?: string
  }
  publisher: {
    name: string
    logo: string
  }
  url: string
}): WithContext<Article> {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: data.headline,
    description: data.description,
    image: data.image,
    datePublished: data.datePublished,
    dateModified: data.dateModified || data.datePublished,
    author: {
      '@type': 'Person',
      name: data.author.name,
      ...(data.author.url && { url: data.author.url })
    },
    publisher: {
      '@type': 'Organization',
      name: data.publisher.name,
      logo: {
        '@type': 'ImageObject',
        url: data.publisher.logo
      }
    },
    url: data.url
  }
}

/**
 * Generate Blog schema for blog listing pages
 * Used on blog index/listing pages to indicate a collection of articles
 */
export function generateBlogSchema(data: {
  name: string
  description: string
  url: string
  publisher: {
    name: string
    logo: string
  }
}): WithContext<Blog> {
  return {
    '@context': 'https://schema.org',
    '@type': 'Blog',
    name: data.name,
    description: data.description,
    url: data.url,
    publisher: {
      '@type': 'Organization',
      name: data.publisher.name,
      logo: {
        '@type': 'ImageObject',
        url: data.publisher.logo
      }
    }
  }
}

/**
 * Generate BreadcrumbList schema for navigation SEO
 * Used on blog post pages (Home > Blog > Post)
 */
export function generateBreadcrumbSchema(data: { items: { name: string; url: string }[] }): WithContext<BreadcrumbList> {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: data.items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url
    }))
  }
}
