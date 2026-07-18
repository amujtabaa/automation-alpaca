import { Slot } from '@radix-ui/react-slot'

import { docs } from '@/app/source'
import Logo from '@/components/logo' // TODO: your nav logo component

import type { DocsLayoutProps } from 'fumadocs-ui/layouts/docs'
import type { HomeLayoutProps } from 'fumadocs-ui/layouts/home'

export const baseOptions: HomeLayoutProps = {
  nav: {
    // Don't wrap in Link - Fumadocs already wraps nav.title in a Link
    title: <Logo />,
    url: '/',
    transparentMode: 'top'
  },
  // Hide nav links menu entirely (removes triple dots menu)
  links: []
}

export const docsOptions: DocsLayoutProps = {
  ...baseOptions,
  tree: docs.pageTree,
  // Override layout to be full-width (edge-to-edge sidebar/toc) + match sidebar/TOC widths
  containerProps: {
    className: 'md:layout:[--fd-sidebar-width:340px] xl:[--fd-toc-width:340px] [--fd-layout-width:100vw]'
  },
  sidebar: {
    tabs: {
      transform(option, node) {
        const meta = docs.getNodeMeta(node)
        if (!meta) return option

        // v16: meta.file.dirname was removed - derive folder name from meta.path ("guide/meta.json" -> "guide")
        const dirname = meta.path.split("/").slice(0, -1).join("/")

        return {
          ...option,
          icon: (
            <Slot
              className='from-fd-background/80 size-9 shrink-0 rounded-md bg-gradient-to-t p-1.5'
              style={{
                color: `hsl(var(--${dirname}-color))`,
                backgroundColor: `hsl(var(--${dirname}-color)/.3)`
              }}
            >
              {node.icon}
            </Slot>
          )
        }
      }
    }
  }
}
