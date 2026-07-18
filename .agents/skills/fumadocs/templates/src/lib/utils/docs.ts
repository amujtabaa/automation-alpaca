import type * as PageTree from 'fumadocs-core/page-tree'

export function findRoot(items: PageTree.Node[], pathname: string): PageTree.Folder | undefined {
  for (const item of items) {
    if (item.type === 'folder') {
      const root = findRoot(item.children, pathname)

      if (root) return root
      if (item.root === true && hasActive(item.children, pathname)) {
        return item
      }
    }
  }
}

export function hasActive(items: PageTree.Node[], url: string): boolean {
  return items.some(item => {
    if (item.type === 'page') {
      return item.url === url
    }

    if (item.type === 'folder') return item.index?.url === url || hasActive(item.children, url)

    return false
  })
}

const filterSiblings = (children: PageTree.Node[], pathname: string) => {
  return children.filter(c => c.type === 'page' && c.url !== pathname && !c.external)
}

export const findSiblings = (children: PageTree.Node[], pathname: string): PageTree.Node[] => {
  for (const child of children) {
    if (child.type === 'folder') {
      if (child.index?.url === pathname) {
        return filterSiblings(child.children, pathname)
      }

      const siblings = findSiblings(child.children, pathname)

      if (siblings.length > 0) return siblings
    }

    if (child.type === 'page' && child.url === pathname) {
      return filterSiblings(
        children.map(child => {
          if (child.type === 'folder' && child.index) {
            return child.index
          }

          return child
        }),
        pathname
      )
    }
  }

  return []
}
