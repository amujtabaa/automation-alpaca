const DOCS_PREFIX = '/blog'

const pathsConfig = {
  index: '/',
  docs: {
    index: `${DOCS_PREFIX}`
  }
} as const

export { pathsConfig, DOCS_PREFIX }
