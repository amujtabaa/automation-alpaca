// Fumadocs v16 with Tailwind 4 preset approach
// CSS handled globally in globals.css via @import 'fumadocs-ui/css/preset.css'

import { DocsLayout } from 'fumadocs-ui/layouts/docs'
import { RootProvider } from 'fumadocs-ui/provider/next'
import type { ReactNode } from 'react'

import { docsOptions } from '@/app/blog/layout.config'

// This layout applies to doc pages under /blog/[...slug]
// The landing page at /blog is at (pages)/blog/page.tsx with header/footer
export default function Layout({ children }: { children: ReactNode }): React.ReactElement {
  return (
    <RootProvider>
      <DocsLayout {...docsOptions}>{children}</DocsLayout>
    </RootProvider>
  )
}
