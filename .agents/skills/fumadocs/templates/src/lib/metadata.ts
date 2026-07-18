import type { Metadata } from 'next'

type OpenGraphType = 'article' | 'website' | 'profile'

interface Image {
  url: string | URL
  secureUrl?: string | URL
  alt?: string
  type?: string
  width?: string | number
  height?: string | number
}

interface SeoProps {
  readonly title?: string
  readonly description?: string
  readonly image?: Image
  readonly url?: string
  readonly type?: OpenGraphType
  readonly canonical?: string
}

export const SITE_NAME = 'Acme'

// SEO titles no longer include site suffix - full 60 chars available for title
// Brand visibility moved to the description prefix ("Acme | ...")
export const SITE_NAME_TEMPLATE = '%s'

export const publicUrl = process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'

const DEFAULT_TITLE = 'Acme - Your Product Tagline' // TODO: site default title
const DEFAULT_DESCRIPTION = 'What Acme does and who it is for.'

// Version for cache busting OG image - increment when image changes
const OG_IMAGE_VERSION = 'v1'

// Ensure OpenGraph image never uses localhost in production
const getImageUrl = (): string => {
  const baseUrl = publicUrl.includes('localhost') && typeof window === 'undefined' ? 'https://acme.com' : publicUrl
  return `${baseUrl}/opengraph-image.png?${OG_IMAGE_VERSION}`
}

const DEFAULT_IMAGE = {
  url: getImageUrl(),
  width: 1200,
  height: 630
}

export const getMetadata = (
  {
    title = DEFAULT_TITLE,
    description = DEFAULT_DESCRIPTION,
    url,
    canonical,
    image = DEFAULT_IMAGE,
    type = 'website'
  } = {} as SeoProps
): Metadata => ({
  title,
  description,
  openGraph: {
    title,
    url: url ?? canonical ?? publicUrl,
    description,
    siteName: SITE_NAME,
    images: image,
    type
  },
  ...{
    ...(canonical && {
      alternates: {
        canonical
      }
    })
  },
  twitter: {
    images: image,
    card: 'summary_large_image'
  }
})
