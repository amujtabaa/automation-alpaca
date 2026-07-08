'use client'

import { usePagination } from '@mantine/hooks'
import { ArrowLeftIcon, ArrowRightIcon } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useFilters } from '@/contexts/filter-context'

type PaginationLinkProps = {
  isDisabled?: boolean
  children: React.ReactNode
  page?: number
  prefix?: React.ReactNode
  suffix?: React.ReactNode
  isActive?: boolean
  className?: string
  onPageChange: (page: number) => void
}

const PaginationLink = ({
  isDisabled,
  children,
  prefix,
  suffix,
  page,
  isActive,
  className,
  onPageChange
}: PaginationLinkProps) => {
  if (isDisabled) {
    return (
      <Button variant='ghost' size='sm' disabled className={className}>
        {prefix}
        {children}
        {suffix}
      </Button>
    )
  }

  return (
    <Button
      variant='ghost'
      size='sm'
      onClick={() => onPageChange(page!)}
      className={cn(isActive && 'bg-accent', className)}
    >
      {prefix}
      {children}
      {suffix}
    </Button>
  )
}

export type PaginationProps = ComponentProps<'nav'> & {
  total: number
  perPage?: number
  page?: number
  siblings?: number
  boundaries?: number
}

export const Pagination = ({
  className,
  total,
  perPage = 1,
  page = 1,
  siblings,
  boundaries,
  ...props
}: PaginationProps) => {
  const { updateFilters } = useFilters()
  const pageCount = Math.ceil(total / perPage)

  const pagination = usePagination({
    total: pageCount,
    page,
    siblings,
    boundaries
  })

  const handlePageChange = (newPage: number) => {
    if (newPage <= 1) {
      updateFilters({ page: null })
    } else {
      updateFilters({ page: newPage })
    }
  }

  if (pagination.range.length <= 1) {
    return null
  }

  return (
    <nav
      className={cn('-mt-px flex w-full items-center justify-between gap-3 text-sm md:w-auto', className)}
      {...props}
    >
      <PaginationLink
        isDisabled={page <= 1}
        page={page - 1}
        onPageChange={handlePageChange}
        prefix={<ArrowLeftIcon className='size-4' />}
      >
        Prev
      </PaginationLink>

      <div className='text-muted-foreground text-sm md:hidden'>
        Page {page} of {pageCount}
      </div>

      <div className='flex flex-wrap items-center gap-2 max-md:hidden'>
        <span className='text-muted-foreground text-sm'>Page:</span>

        {pagination.range.map((value, index) => (
          <div key={`page-${index}`}>
            {value === 'dots' && <span className='text-muted-foreground px-3'>...</span>}

            {typeof value === 'number' && (
              <PaginationLink
                page={value}
                onPageChange={handlePageChange}
                isActive={value === page}
                className={cn('min-w-8 justify-center')}
              >
                {value}
              </PaginationLink>
            )}
          </div>
        ))}
      </div>

      <PaginationLink
        isDisabled={page >= pageCount}
        page={page + 1}
        onPageChange={handlePageChange}
        suffix={<ArrowRightIcon className='size-4' />}
      >
        Next
      </PaginationLink>
    </nav>
  )
}
