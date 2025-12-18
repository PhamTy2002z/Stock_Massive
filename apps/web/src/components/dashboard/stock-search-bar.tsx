"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Search, Loader2 } from "lucide-react"

import { Input } from "@/components/ui/input"
import { searchStocks, StockSymbol } from "@/lib/api"

interface StockSearchBarProps {
  onSelect?: (symbol: StockSymbol) => void
  placeholder?: string
  className?: string
}

export function StockSearchBar({
  onSelect,
  placeholder = "Search stocks...",
  className = "",
}: StockSearchBarProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<StockSymbol[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Debounced search
  useEffect(() => {
    if (query.length < 1) {
      setResults([])
      setIsOpen(false)
      return
    }

    const timer = setTimeout(async () => {
      setIsLoading(true)
      try {
        const data = await searchStocks(query, 10)
        setResults(data)
        setIsOpen(data.length > 0)
        setSelectedIndex(-1)
      } catch (error) {
        console.error("Search error:", error)
        setResults([])
      } finally {
        setIsLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleSelect = useCallback(
    (symbol: StockSymbol) => {
      setQuery(symbol.symbol)
      setIsOpen(false)
      onSelect?.(symbol)
    },
    [onSelect]
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || results.length === 0) return

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault()
        setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev))
        break
      case "ArrowUp":
        e.preventDefault()
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev))
        break
      case "Enter":
        e.preventDefault()
        if (selectedIndex >= 0 && selectedIndex < results.length) {
          handleSelect(results[selectedIndex])
        }
        break
      case "Escape":
        setIsOpen(false)
        break
    }
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          className="h-9 w-64 pl-9 lg:w-80 bg-muted/50 border-transparent focus:bg-background focus:border-input transition-all duration-200"
        />
        {isLoading && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 max-h-80 overflow-auto rounded-md border bg-popover shadow-lg z-50">
          {results.map((item, index) => (
            <button
              key={item.symbol}
              type="button"
              onClick={() => handleSelect(item)}
              className={`w-full px-3 py-2 text-left hover:bg-accent transition-colors ${
                index === selectedIndex ? "bg-accent" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm">{item.symbol}</span>
                {item.exchange && (
                  <span className="text-xs text-muted-foreground">{item.exchange}</span>
                )}
              </div>
              {item.organ_name && (
                <p className="text-xs text-muted-foreground truncate mt-0.5">
                  {item.organ_name}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
