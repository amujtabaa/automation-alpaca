'use client'

import { type PropsWithChildren, useDeferredValue } from 'react'
import { Input } from '@/components/ui/input'
import { Pagination, type PaginationProps } from '@/components/pagination'
import { BlogListSkeleton } from './blog-list'
import { BlogSearch, type BlogSearchProps } from './blog-search'
import { FiltersProvider, useFilters, type FiltersProviderProps } from '@/contexts/filter-context'
import { blogFilterParams, type BlogFilterSchema } from '@/lib/blog-schema'

type BlogListingProps = PropsWithChildren & {
  pagination: PaginationProps
  search?: BlogSearchProps
  options?: Omit<FiltersProviderProps, 'schema'>
}

const BlogContent = ({ children }: PropsWithChildren) => {
  const { filters } = useFilters<BlogFilterSchema>()
  const deferredSort = useDeferredValue(filters.sort)

  return <div key={deferredSort}>{children}</div>
}

const BlogListing = ({ children, pagination, options, search }: BlogListingProps) => {
  return (
    <FiltersProvider schema={blogFilterParams} {...options}>
      <div className='space-y-6' id='docs'>
        <BlogSearch {...search} />
        <BlogContent>{children}</BlogContent>
      </div>

      <Pagination {...pagination} className='mt-8' />
    </FiltersProvider>
  )
}

const BlogListingSkeleton = () => {
  return (
    <div className='space-y-6'>
      <Input placeholder='Loading...' disabled />
      <BlogListSkeleton />
    </div>
  )
}

export { BlogListing, BlogListingSkeleton, type BlogListingProps }
