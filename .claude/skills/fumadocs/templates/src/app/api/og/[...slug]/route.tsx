import { notFound } from 'next/navigation'
import { ImageResponse } from 'next/og'
import { readFileSync } from 'node:fs'
import path from 'node:path'

import { docs } from '@/app/source'

import type { NextRequest } from 'next/server'

// Version for cache busting dynamic OG images - increment when design changes
export const OG_DYNAMIC_VERSION = 'v1'

const regularFont = readFileSync(path.join(process.cwd(), 'src/app/api/og/[...slug]/GeneralSans-Regular.woff'))

export const GET = async (_: NextRequest, { params }: { params: Promise<{ slug: string[] }> }) => {
  const slugs = (await params).slug.slice(0, -1)

  const page = docs.getPage(slugs)

  if (!page) notFound()

  // Scale font sizes down for long titles to prevent overlap
  const title = (page.data.heading || page.data.title) as string
  const titleLen = title.length
  const titleSize = titleLen > 70 ? 55 : titleLen > 50 ? 65 : 85
  const descSize = titleLen > 70 ? 32 : titleLen > 50 ? 38 : 48

  // TODO: in the JSX below, bg-[#2B2B2B] = your DARK theme background hex
  return new ImageResponse(
    (
      <div
        tw='flex flex-col w-full h-full bg-[#2B2B2B] text-white'
        style={{
          backgroundImage: `linear-gradient(to left bottom, rgba(255,255,255,0.08), transparent)`
        }}
      >
        <GridPattern
          squares={[
            [0, 2],
            [4, 3],
            [1, 1],
            [3, 0]
          ]}
        />
        <div tw='flex flex-col w-full h-full p-16'>
          <div tw='flex flex-row justify-between items-center mb-3'>
            <div tw='flex flex-row items-center'>
              {/* TODO: replace with YOUR logo - simple SVG paths only (no foreignObject, no external images) */}
              <div
                tw='flex items-center justify-center rounded-full'
                style={{
                  width: 65,
                  height: 65,
                  backgroundColor: '#C96F4A' // TODO: your brand accent color
                }}
              >
                <svg
                  width='40'
                  height='40'
                  viewBox='0 0 24 24'
                  fill='none'
                  stroke='white'
                  stroke-width='2'
                  stroke-linecap='round'
                  stroke-linejoin='round'
                >
                  <path d='M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5' />
                  <path d='M9 18h6' />
                  <path d='M10 22h4' />
                </svg>
              </div>

              <p tw='text-5xl font-bold ml-6'>Acme</p>
            </div>
          </div>

          <p tw='font-bold mt-auto mb-1' style={{ fontSize: titleSize, lineHeight: 1.1 }}>
            {title}
          </p>
          <p tw='text-[rgba(240,240,240,0.8)]' style={{ fontSize: descSize, lineHeight: 1.25 }}>
            {page.data.description}
          </p>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: [
        {
          name: 'General Sans Regular',
          data: regularFont,
          weight: 400
        }
      ]
    }
  )
}

export function generateStaticParams() {
  return docs.generateParams().map(params => ({
    ...params,
    slug: [...params.slug, 'og.png']
  }))
}

interface GridPatternProps {
  width?: number
  height?: number
  x?: number
  y?: number
  squares?: [x: number, y: number][]
  strokeDasharray?: number
  className?: string
}

export function GridPattern({
  width = 100,
  height = 100,
  x = -1,
  y = -1,
  squares,
  strokeDasharray,
  ...props
}: GridPatternProps) {
  return (
    <svg
      fill='rgba(156, 163, 175, 0.15)'
      stroke='rgba(156, 163, 175, 0.2)'
      style={{
        position: 'absolute',
        width: '100%',
        height: '100%',
        top: 0,
        maskImage: 'radial-gradient(circle at 0% 100%, white, transparent)'
      }}
      viewBox='0 0 600 400'
      {...props}
    >
      <defs>
        <pattern id='og-pattern' width={width} height={height} patternUnits='userSpaceOnUse'>
          <path
            d={`M.5 ${height.toString()}V.5H${width.toString()}`}
            fill='none'
            strokeWidth={1}
            strokeDasharray={strokeDasharray}
          />
        </pattern>
      </defs>
      <rect width='600' height='600' strokeWidth={0} fill='url(#og-pattern)' x={x} y={y} />
      {squares?.map(([itemX, itemY]) => (
        <rect
          strokeWidth='0'
          key={`${itemX.toString()}-${itemY.toString()}`}
          width={width - 1}
          height={height}
          x={itemX * width + 1}
          y={itemY * (height + 1)}
        />
      ))}
    </svg>
  )
}
