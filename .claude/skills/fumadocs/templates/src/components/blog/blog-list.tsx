import type { ComponentProps } from 'react'

import { BlogCard, BlogCardSkeleton } from './blog-card'
import { cn } from '@/lib/utils'
import type { BlogCardData } from '@/lib/blog-data'

export type BlogListProps = ComponentProps<'div'> & {
  blogs: BlogCardData[]
}

export const BlogList = ({ children, blogs, className, ...props }: BlogListProps) => {
  return (
    <div className={cn('grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3', className)} {...props}>
      {blogs.map((blog, index) => (
        <BlogCard key={blog.slug} blog={blog} style={{ order: index }} />
      ))}

      {blogs.length === 0 && (
        <div className='text-muted-foreground col-span-full py-12 text-center'>
          No posts found for the given filters.
        </div>
      )}

      {children}
    </div>
  )
}

export const BlogListSkeleton = ({ count = 6 }: { count?: number }) => {
  return (
    <div className='grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3'>
      {[...Array(count)].map((_, index) => (
        <BlogCardSkeleton key={index} />
      ))}
    </div>
  )
}
