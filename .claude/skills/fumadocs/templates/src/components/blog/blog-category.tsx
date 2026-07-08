import { Card, Cards } from 'fumadocs-ui/components/card'

import { docs } from '@/app/source'
import { findRoot, findSiblings } from '@/lib/utils/docs'

import type { Page } from 'fumadocs-core/source'
import type { HTMLAttributes } from 'react'

export function BlogCategory({
  page,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  page: Page
}): React.ReactElement {
  const pages = docs.getPages()

  const root = findRoot(docs.pageTree.children, page.url)
  const siblings = findSiblings(root?.children ?? [], page.url)

  const siblingPages = siblings
    .map(sibling => pages.find(p => 'url' in sibling && p.url === sibling.url))
    .filter((p): p is ReturnType<typeof docs.getPages>[number] => !!p)

  const filtered = siblingPages.filter(item => !page.data.icon || (page.data.icon && item.data.icon))

  return (
    <Cards {...props}>
      {filtered.map(item => (
        <Card key={item.url} title={item.data.title} description={item.data.description} href={item.url} />
      ))}
    </Cards>
  )
}
