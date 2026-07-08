'use client'

import type { ComponentProps } from 'react'
import { BookOpen, Wrench, Brain, FileText, Eye } from 'lucide-react'
import Link from 'next/link'

import { Card, CardDescription, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { BlogCardData } from '@/lib/blog-data'

type BlogCardProps = ComponentProps<typeof Card> & {
  blog: BlogCardData
}

/**
 * Get section-specific icon based on the core section
 */
const getSectionIcon = (coreSection: string | null) => {
  if (!coreSection) return FileText

  const section = coreSection.toLowerCase()

  // TODO: one case per root content folder (matches blog-structure.ts sections)
  switch (section) {
    case 'guide':
      return BookOpen
    case 'tutorials':
      return Brain
    case 'comparisons':
      return Wrench
    default:
      return FileText
  }
}

export const BlogCard = ({ blog, className, ...props }: BlogCardProps) => {
  const IconComponent = getSectionIcon(blog.coreSection)

  return (
    <Card
      className={cn(
        'group relative flex flex-col gap-4 p-5',
        'hover:bg-primary/5 hover:border-primary/20 hover:shadow-md',
        'transition-all duration-200',
        className
      )}
      {...props}
    >
      {/* Header: Icon + Title */}
      <CardHeader className='space-y-0 p-0'>
        <div className='flex items-center gap-3'>
          <div className='bg-primary/10 flex size-10 shrink-0 items-center justify-center rounded-xl'>
            <IconComponent className='text-primary size-5' />
          </div>

          <h3 className='flex-1 truncate text-lg leading-tight font-semibold'>
            <Link href={`/blog/${blog.slug}`}>
              <span className='absolute inset-0 z-10' />
              {blog.name}
            </Link>
          </h3>
        </div>
      </CardHeader>

      {/* Content area with hover reveal */}
      <div className='relative min-h-[4.5rem] flex-1'>
        {/* Default state: Tagline + Badges */}
        <div className='flex flex-col gap-3 duration-200 group-hover:opacity-0'>
          {blog.tagline && <CardDescription className='line-clamp-2 text-sm/relaxed'>{blog.tagline}</CardDescription>}

          {/* Badge row */}
          <div className='mt-auto flex flex-wrap gap-2'>
            {blog.coreSection && (
              <Badge variant='secondary' className='text-xs'>
                {blog.coreSection}
              </Badge>
            )}
            {blog.subsection && (
              <Badge variant='secondary' className='text-xs'>
                {blog.subsection}
              </Badge>
            )}
          </div>
        </div>

        {/* Hover state: Full description */}
        {blog.description && (
          <div className='absolute inset-0 opacity-0 duration-200 group-hover:opacity-100'>
            <CardDescription className='text-foreground/80 line-clamp-4 text-sm/relaxed'>
              {blog.description}
            </CardDescription>
          </div>
        )}
      </div>

      {/* Footer: Views + Date */}
      <div className='text-muted-foreground group-hover:text-foreground/60 flex items-center gap-3 pt-2 text-xs transition-colors'>
        {blog.views != null && blog.views > 0 && (
          <span className='flex items-center gap-1'>
            <Eye className='size-3.5' />
            {blog.views.toLocaleString()}
          </span>
        )}
        {blog.publishedAt && (
          <time dateTime={blog.publishedAt.toISOString()}>
            {new Intl.DateTimeFormat('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric'
            }).format(blog.publishedAt)}
          </time>
        )}
      </div>
    </Card>
  )
}

export const BlogCardSkeleton = () => {
  return (
    <Card className='flex flex-col gap-4 p-5 select-none'>
      {/* Header skeleton */}
      <div className='flex items-center gap-3'>
        <div className='bg-muted size-10 shrink-0 animate-pulse rounded-xl' />
        <div className='bg-muted h-5 w-2/3 animate-pulse rounded'>&nbsp;</div>
      </div>

      {/* Content skeleton */}
      <div className='space-y-3'>
        <div className='space-y-2'>
          <div className='bg-muted h-4 w-full animate-pulse rounded'>&nbsp;</div>
          <div className='bg-muted h-4 w-4/5 animate-pulse rounded'>&nbsp;</div>
        </div>

        <div className='flex gap-2'>
          {[...Array(2)].map((_, index) => (
            <Badge key={index} variant='outline' className='h-5 w-14'>
              &nbsp;
            </Badge>
          ))}
        </div>
      </div>
    </Card>
  )
}
