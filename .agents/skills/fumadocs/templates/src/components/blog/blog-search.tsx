'use client'

import { useEffect, useMemo } from 'react'
import type { ComponentProps } from 'react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { Clock, Flame } from 'lucide-react'
import { Filters } from '@/components/filters/filters'
import { useFilters } from '@/contexts/filter-context'
import type { BlogFilterSchema } from '@/lib/blog-schema'
import { getUniqueSections, getUniqueCategories } from '@/lib/blog-data'

export type BlogSearchProps = ComponentProps<'div'> & {
  placeholder?: string
}

export const BlogSearch = ({ placeholder, ...props }: BlogSearchProps) => {
  const { filters, updateFilters } = useFilters<BlogFilterSchema>()

  const isPopular = filters.sort === 'views.desc'

  // Get all available sections
  const sections = useMemo(() => getUniqueSections(), [])

  // Get categories dynamically based on selected section
  const availableCategories = useMemo(() => getUniqueCategories(filters.section || undefined), [filters.section])

  // Clear category if it's not available in the newly selected section
  useEffect(() => {
    if (filters.category && filters.section) {
      const categoryExists = availableCategories.some(cat => cat.toLowerCase() === filters.category.toLowerCase())
      if (!categoryExists) {
        updateFilters({ category: '' })
      }
    }
  }, [filters.section, filters.category, availableCategories, updateFilters])

  return (
    <Filters placeholder={placeholder || 'Search posts...'} {...props}>
      {/* Section + Category Filters */}
      <div className='flex w-full gap-2 sm:contents sm:w-auto'>
        <Select
          key={`section-${filters.section || 'all'}`}
          value={filters.section && filters.section.trim() !== '' ? filters.section : undefined}
          onValueChange={section => updateFilters({ section })}
        >
          <SelectTrigger className='bg-background h-10! w-auto rounded-2xl px-4 py-2 max-sm:flex-1 sm:min-w-40'>
            <SelectValue placeholder='All Sections' />
          </SelectTrigger>
          <SelectContent className='rounded-xl'>
            {sections.map(section => (
              <SelectItem key={section.toLowerCase()} value={section.toLowerCase()} className='rounded-lg'>
                {section}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {availableCategories.length > 0 && (
          <Select
            key={`category-${filters.category || 'all'}`}
            value={filters.category && filters.category.trim() !== '' ? filters.category : undefined}
            onValueChange={category => updateFilters({ category })}
          >
            <SelectTrigger className='bg-background h-10! w-auto rounded-2xl px-4 py-2 max-sm:flex-1 sm:min-w-40'>
              <SelectValue placeholder='All Categories' />
            </SelectTrigger>
            <SelectContent className='rounded-xl'>
              {availableCategories.map(category => (
                <SelectItem key={category.toLowerCase()} value={category.toLowerCase()} className='rounded-lg'>
                  {category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Sort Mode Toggle */}
      <div className='border-input flex h-10 w-full overflow-hidden rounded-2xl border sm:w-auto'>
        <button
          type='button'
          onClick={() => updateFilters({ sort: 'publishedAt.desc' })}
          className={cn(
            'flex flex-1 items-center justify-center gap-1.5 px-4 text-sm font-medium transition-colors sm:flex-initial',
            !isPopular
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Clock className='size-3.5' />
          Most Recent
        </button>
        <button
          type='button'
          onClick={() => updateFilters({ sort: 'views.desc' })}
          className={cn(
            'border-input flex flex-1 items-center justify-center gap-1.5 border-l px-4 text-sm font-medium transition-colors sm:flex-initial',
            isPopular
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          <Flame className='size-3.5' />
          Most Popular
        </button>
      </div>
    </Filters>
  )
}
