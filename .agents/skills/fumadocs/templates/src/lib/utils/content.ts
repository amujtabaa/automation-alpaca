import { exec } from 'child_process'
import fs from 'fs'
import path from 'path'
import { promisify } from 'util'
import grayMatter from 'gray-matter'

const execPromise = promisify(exec)

/**
 * Get the last modified date from git history or file system
 */
export const getLastModifiedAt = async (filePath: string) => {
  try {
    // Try to get git last modified date
    // Use relative path from process.cwd() for better cross-platform compatibility
    const relativePath = path.relative(process.cwd(), filePath).replace(/\\/g, '/')
    const { stdout } = await execPromise(`git log -1 --format=%ai -- "${relativePath}"`, {
      cwd: process.cwd()
    })

    if (stdout && stdout.trim()) {
      return new Date(stdout.trim()).toISOString()
    }
  } catch {
    // Git not available or file not in git history
    // Silently fallback to file system stats
  }

  try {
    // Fallback to file system modification time
    const stats = fs.statSync(filePath)
    return stats.mtime.toISOString()
  } catch {
    // If file doesn't exist or other error, use current time silently
    return new Date().toISOString()
  }
}

/**
 * Get mirror document content from another file
 */
export const getMirrorDoc = (rootDir: string, filePath: string, mirrorPath: string) => {
  const mirror = path.resolve(`${rootDir}/${path.dirname(filePath)}`, mirrorPath)

  try {
    const content = fs.readFileSync(mirror, 'utf-8')
    const matter = grayMatter(content)
    return matter
  } catch {
    // If mirror file doesn't exist, return empty content
    // This prevents ENOENT errors during build
    return {
      content: '',
      data: {},
      excerpt: '',
      orig: ''
    }
  }
}
