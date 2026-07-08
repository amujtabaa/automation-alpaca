'use client'

import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

const TOPICS = ['Guides', 'Tips', 'Tutorials', 'Insights', 'Updates', 'Resources']

export const BlogHeading = () => {
  const ref = useRef<HTMLDivElement>(null)
  const [activeTopic, setActiveTopic] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    if (ref.current) {
      setRect(ref.current.children[activeTopic]?.getBoundingClientRect() ?? null)
    }
  }, [activeTopic])

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveTopic(prev => (prev + 1) % TOPICS.length)
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  return (
    <h1 className='relative mx-auto max-w-5xl text-center text-3xl font-medium tracking-tight text-balance sm:text-4xl md:text-5xl lg:text-6xl'>
      <span>Acme </span>
      <span className='inline-flex items-baseline justify-center gap-3 sm:gap-4 md:gap-5'>
        <span className='relative flex px-1.5 py-[1px] sm:px-2 md:px-3 md:py-0.5'>
          <span
            className='bg-primary absolute inset-0 -z-10 -rotate-1 rounded-sm'
            style={{ transitionDuration: '3.5s' }}
          ></span>

          <span
            className='relative inline-block overflow-hidden transition-[width,height] duration-500'
            style={{
              width: rect?.width,
              height: rect?.height
            }}
          >
            <span className='pointer-events-none relative -z-20 px-1 select-none'>{TOPICS[activeTopic]}</span>

            <div
              className={cn('absolute top-0 left-0 flex flex-col items-start', {
                'transition-transform duration-500': activeTopic !== 0
              })}
              aria-hidden='true'
              style={{
                transform: `translateY(-${(rect?.height ?? 0) * activeTopic}px)`
              }}
              ref={ref}
            >
              {TOPICS.map((topic, index) => (
                <span
                  key={index}
                  className={cn(
                    'text-primary-foreground selection:bg-background selection:text-primary inline-block px-1 text-left',
                    {
                      'pointer-events-none select-none': index !== activeTopic
                    }
                  )}
                >
                  {topic}
                </span>
              ))}
            </div>
          </span>
        </span>
      </span>
    </h1>
  )
}
