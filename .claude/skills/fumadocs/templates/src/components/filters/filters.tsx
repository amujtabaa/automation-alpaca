'use client'

import { LoaderIcon, SearchIcon, XIcon } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useFilters } from '@/contexts/filter-context'

export type FiltersProps = Omit<ComponentProps<'div'>, 'children'> & {
  placeholder: string
  children?: React.ReactNode
}

export const Filters = ({ children, className, placeholder, ...props }: FiltersProps) => {
  const { filters, isLoading, isDefault, updateFilters } = useFilters()

  return (
    <div className={cn('flex w-full flex-wrap gap-2', className)} {...props}>
      <div className='relative min-w-0 grow'>
        <div className='pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 opacity-50'>
          {isLoading ? <LoaderIcon className='size-4 animate-spin' /> : <SearchIcon className='size-4' />}
        </div>

        <Input
          value={filters.q || ''}
          onChange={e => updateFilters({ q: e.target.value })}
          placeholder={isLoading ? 'Loading...' : placeholder}
          className={cn('bg-background h-10 w-full truncate rounded-2xl px-4 pl-10', !isDefault && 'pr-12 sm:pr-20')}
        />

        {!isDefault && (
          <Button
            variant='ghost'
            size='sm'
            className='absolute inset-y-2 right-2 h-auto'
            onClick={() => updateFilters(null)}
            aria-label='Reset filters'
          >
            <XIcon className='mr-1 size-4' />
            <span className='max-md:sr-only'>Reset</span>
          </Button>
        )}
      </div>

      {children}
    </div>
  )
}
