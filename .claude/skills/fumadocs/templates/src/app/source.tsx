import { createMDXSource } from '@fumadocs/content-collections'
import { allDocs, allMetas } from 'content-collections'
import { loader } from 'fumadocs-core/source'
import { icons as lucideIcons, type LucideIcon } from 'lucide-react'

import { DOCS_PREFIX } from '@/config/paths'

export const docs = {
  ...loader({
    baseUrl: DOCS_PREFIX,
    icon(icon) {
      if (!icon) return

      // Use lucide-react icons
      if (icon in lucideIcons) {
        const Icon = lucideIcons[icon as keyof typeof lucideIcons] as LucideIcon
        return <Icon />
      }
    },
    source: createMDXSource(allDocs, allMetas)
  })
}
