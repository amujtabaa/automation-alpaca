import { createSearchParamsCache, parseAsInteger, parseAsString } from 'nuqs/server'

// Blog filter parameters schema
export const blogFilterParams = {
  q: parseAsString.withDefault(''),
  sort: parseAsString.withDefault(''),
  page: parseAsInteger.withDefault(1),
  perPage: parseAsInteger.withDefault(24),
  section: parseAsString.withDefault(''),
  category: parseAsString.withDefault('')
}

// Type for the filter parameters
export type BlogFilterSchema = typeof blogFilterParams
export type BlogFilterParams = {
  q: string
  sort: string
  page: number
  perPage: number
  section: string
  category: string
}

// Cache for parsing search params
export const blogFilterParamsCache = createSearchParamsCache(blogFilterParams)
