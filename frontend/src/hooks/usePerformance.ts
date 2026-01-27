import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Hook para debounce de valores
 * Útil para inputs de busca para evitar requisições excessivas
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

/**
 * Hook para throttle de funções
 * Limita a frequência de execução de uma função
 */
export function useThrottle<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number = 300
): T {
  const lastRan = useRef(Date.now())
  const timeoutRef = useRef<NodeJS.Timeout>()

  const throttledCallback = useCallback(
    (...args: Parameters<T>) => {
      const now = Date.now()
      const timeSinceLastRan = now - lastRan.current

      if (timeSinceLastRan >= delay) {
        lastRan.current = now
        callback(...args)
      } else {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current)
        }
        timeoutRef.current = setTimeout(() => {
          lastRan.current = Date.now()
          callback(...args)
        }, delay - timeSinceLastRan)
      }
    },
    [callback, delay]
  ) as T

  return throttledCallback
}

/**
 * Hook para lazy loading de componentes pesados
 * Adia o carregamento até que o componente esteja visível
 */
export function useIntersectionObserver(
  options: IntersectionObserverInit = {}
): [React.RefObject<HTMLDivElement>, boolean] {
  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true)
        observer.disconnect()
      }
    }, options)

    if (ref.current) {
      observer.observe(ref.current)
    }

    return () => observer.disconnect()
  }, [options])

  return [ref, isVisible]
}

/**
 * Hook para memoização de callbacks pesados
 */
export function useMemoizedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  deps: React.DependencyList
): T {
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback, ...deps])

  return useCallback(
    ((...args) => callbackRef.current(...args)) as T,
    []
  )
}
