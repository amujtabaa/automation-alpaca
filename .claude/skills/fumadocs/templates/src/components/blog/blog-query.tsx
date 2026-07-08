import type { SearchParams } from 'nuqs'
import { BlogList, type BlogListProps } from './blog-list'
import { BlogListing, type BlogListingProps } from './blog-listing'
import type { PaginationProps } from '@/components/pagination'
import { blogFilterParamsCache } from '@/lib/blog-schema'
import type { BlogFilterParams } from '@/lib/blog-schema'
import { searchBlogs } from '@/lib/blog-data'

type BlogQueryProps = Omit<BlogListingProps, 'pagination'> & {
  searchParams: Promise<SearchParams>
  overrideParams?: Partial<BlogFilterParams>
  list?: Partial<Omit<BlogListProps, 'blogs'>>
  pagination?: Partial<Omit<PaginationProps, 'total' | 'perPage'>>
}

const BlogQuery = async ({ searchParams, overrideParams, list, pagination, ...props }: BlogQueryProps) => {
  const parsedParams = blogFilterParamsCache.parse(await searchParams)
  const params = { ...parsedParams, ...overrideParams }
  const { blogs, total, page, perPage } = await searchBlogs(params)

  return (
    <BlogListing pagination={{ total, perPage, page, ...pagination }} {...props}>
      <BlogList blogs={blogs} {...list} />
    </BlogListing>
  )
}

export { BlogQuery, type BlogQueryProps }
