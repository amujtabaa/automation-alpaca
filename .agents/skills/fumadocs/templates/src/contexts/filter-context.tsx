'use client'

import { type UseQueryStatesKeysMap, useQueryStates, type Values } from 'nuqs'
import { createContext, type PropsWithChildren, use, useTransition } from 'react'
import { isDefaultState } from '@/lib/parsers'

export type FiltersContextType<T extends UseQueryStatesKeysMap> = {
  filters: Values<T>
  isLoading: boolean
  isDefault: boolean
  enableSort: boolean
  enableFilters: boolean
  updateFilters: (values: Partial<Values<T>> | null) => void
}

const FiltersContext = createContext<FiltersContextType<any>>(null!)

export type FiltersProviderProps<T = any> = {
  schema: T
  enableSort?: boolean
  enableFilters?: boolean
}

const FiltersProvider = <T extends UseQueryStatesKeysMap>({
  children,
  schema,
  enableSort = true,
  enableFilters = false
}: PropsWithChildren<FiltersProviderProps<T>>) => {
  const [isLoading, startTransition] = useTransition()

  const [filters, setFilters] = useQueryStates(schema, {
    shallow: false,
    history: 'push',
    startTransition,
    throttleMs: 250
  })

  const isDefault = isDefaultState(schema as any, filters, ['page', 'perPage', 'sort'])

  const updateFilters = (values: Partial<Values<T>> | null) => {
    if (values === null) {
      setFilters(null)
    } else {
      // Only reset page if we're not explicitly setting it
      if (values.hasOwnProperty('page')) {
        // User is navigating pages - don't reset
        setFilters(prev => ({ ...prev, ...values }))
      } else {
        // User is changing filters - reset to page 1
        setFilters(prev => ({ ...prev, ...values, page: null }))
      }
    }
  }

  return (
    <FiltersContext.Provider
      value={{
        filters,
        isLoading,
        isDefault,
        updateFilters,
        enableSort,
        enableFilters
      }}
    >
      {children}
    </FiltersContext.Provider>
  )
}

function useFilters<T extends UseQueryStatesKeysMap>(): FiltersContextType<T> {
  const context = use(FiltersContext)

  if (context === undefined) {
    throw new Error('useFilters must be used within a FiltersProvider')
  }

  return context
}

export { FiltersProvider, useFilters }
