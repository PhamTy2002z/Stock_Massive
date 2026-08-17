import { describe, expect, it } from "vitest"

import type { FeedNewsItem } from "./api"
import {
  articleKey,
  findArticle,
  formatPublishedDate,
  formatStreamDate,
  parsePublishedAt,
  partitionFeed,
  relatedArticles,
  topSymbols,
} from "./news"

/** One feed item, with only the fields the helpers actually read spelled out. */
function item(overrides: Partial<FeedNewsItem> & { symbol: string; id: number }): FeedNewsItem {
  return {
    title: `Tin ${overrides.symbol} ${overrides.id}`,
    source: "VCI",
    published_at: "2026-06-15 17:09",
    summary: null,
    content: null,
    url: null,
    image_url: null,
    price: null,
    price_change_pct: null,
    ...overrides,
  }
}

/** A feed of `count` items, one symbol each, in the order the API returns them. */
function feed(count: number): FeedNewsItem[] {
  return Array.from({ length: count }, (_, index) =>
    item({ symbol: `S${index}`, id: index }),
  )
}

describe("articleKey", () => {
  it("names an article by symbol and id", () => {
    expect(articleKey(item({ symbol: "VCB", id: 123 }))).toBe("VCB:123")
  })

  it("separates the same id under two symbols", () => {
    expect(articleKey(item({ symbol: "FPT", id: 7 }))).not.toBe(
      articleKey(item({ symbol: "VCB", id: 7 })),
    )
  })
})

describe("findArticle", () => {
  const items = [item({ symbol: "VCB", id: 1 }), item({ symbol: "FPT", id: 2 })]

  it("returns the article a key points at", () => {
    expect(findArticle(items, "FPT:2")?.id).toBe(2)
  })

  it("returns null for a key the feed no longer holds", () => {
    expect(findArticle(items, "VCB:999")).toBeNull()
  })

  it("returns null for no key at all", () => {
    expect(findArticle(items, null)).toBeNull()
  })

  it("returns null on an empty feed", () => {
    expect(findArticle([], "VCB:1")).toBeNull()
  })
})

describe("parsePublishedAt", () => {
  it("reads the wall clock as Ho Chi Minh time", () => {
    // 09:30 in UTC+7 is 02:30 UTC, on any machine running the test.
    expect(parsePublishedAt("2026-08-15 09:30")?.toISOString()).toBe("2026-08-15T02:30:00.000Z")
  })

  it("tolerates an ISO T between the date and the time", () => {
    expect(parsePublishedAt("2026-08-15T09:30")?.toISOString()).toBe("2026-08-15T02:30:00.000Z")
  })

  it("returns null for an empty string", () => {
    expect(parsePublishedAt("")).toBeNull()
  })

  it("returns null for a raw provider string", () => {
    expect(parsePublishedAt("hôm qua")).toBeNull()
    expect(parsePublishedAt("15/08/2026 09:30")).toBeNull()
  })

  it("returns null for a date that does not exist", () => {
    expect(parsePublishedAt("2026-13-01 09:30")).toBeNull()
    expect(parsePublishedAt("2026-02-30 09:30")).toBeNull()
  })
})

describe("formatPublishedDate", () => {
  it("puts the weekday first and the clock last", () => {
    expect(formatPublishedDate("2026-06-15 17:09")).toBe("Thứ Hai, 15/6/2026, 17:09")
  })

  it("keeps midnight on a 24-hour clock", () => {
    expect(formatPublishedDate("2026-06-15 00:05")).toBe("Thứ Hai, 15/6/2026, 00:05")
  })

  it("falls back to the raw string when there is nothing to parse", () => {
    expect(formatPublishedDate("vừa xong")).toBe("vừa xong")
    expect(formatPublishedDate("")).toBe("")
  })
})

describe("formatStreamDate", () => {
  it("pads the day and the month so the gutter aligns", () => {
    expect(formatStreamDate("2026-06-17 08:00")).toBe("17/06/2026")
  })

  it("falls back to the raw string", () => {
    expect(formatStreamDate("không rõ")).toBe("không rõ")
  })
})

describe("partitionFeed", () => {
  it("cuts a full feed into hero, spotlight, grid and stream", () => {
    const parts = partitionFeed(feed(12))

    expect(parts.hero?.id).toBe(0)
    expect(parts.spotlight.map((row) => row.id)).toEqual([1, 2])
    expect(parts.grid.map((row) => row.id)).toEqual([3, 4, 5, 6])
    expect(parts.stream.map((row) => row.id)).toEqual([7, 8, 9, 10, 11])
  })

  it("never repeats an article across two blocks", () => {
    const parts = partitionFeed(feed(12))
    const drawn = [
      ...(parts.hero ? [parts.hero] : []),
      ...parts.spotlight,
      ...parts.grid,
      ...parts.stream,
    ].map(articleKey)

    expect(new Set(drawn).size).toBe(12)
  })

  it("leaves the later blocks empty on a short feed", () => {
    const parts = partitionFeed(feed(2))

    expect(parts.hero?.id).toBe(0)
    expect(parts.spotlight.map((row) => row.id)).toEqual([1])
    expect(parts.grid).toEqual([])
    expect(parts.stream).toEqual([])
  })

  it("has no hero on an empty feed", () => {
    const parts = partitionFeed([])

    expect(parts.hero).toBeNull()
    expect(parts.spotlight).toEqual([])
    expect(parts.grid).toEqual([])
    expect(parts.stream).toEqual([])
  })
})

describe("topSymbols", () => {
  it("orders by how many articles each symbol contributed", () => {
    const items = [
      item({ symbol: "FPT", id: 1 }),
      item({ symbol: "VCB", id: 2 }),
      item({ symbol: "VCB", id: 3 }),
      item({ symbol: "VCB", id: 4 }),
      item({ symbol: "FPT", id: 5 }),
      item({ symbol: "HPG", id: 6 }),
    ]

    expect(topSymbols(items, 6)).toEqual(["VCB", "FPT", "HPG"])
  })

  it("breaks a tie alphabetically so the row does not reshuffle", () => {
    const items = [
      item({ symbol: "VNM", id: 1 }),
      item({ symbol: "HPG", id: 2 }),
      item({ symbol: "ACB", id: 3 }),
    ]

    expect(topSymbols(items, 6)).toEqual(["ACB", "HPG", "VNM"])
  })

  it("stops at the maximum asked for", () => {
    expect(topSymbols(feed(9), 6)).toHaveLength(6)
  })

  it("is empty for an empty feed", () => {
    expect(topSymbols([], 6)).toEqual([])
  })
})

describe("relatedArticles", () => {
  const open = item({ symbol: "VCB", id: 1 })
  const items = [
    open,
    item({ symbol: "FPT", id: 2 }),
    item({ symbol: "VCB", id: 3 }),
    item({ symbol: "HPG", id: 4 }),
    item({ symbol: "VCB", id: 5 }),
  ]

  it("puts the same symbol first and never the article itself", () => {
    expect(relatedArticles(items, open, 3).map((row) => row.id)).toEqual([3, 5, 2])
  })

  it("pads with the newest others when the symbol has nothing else", () => {
    const only = item({ symbol: "SSI", id: 9 })
    expect(relatedArticles([only, ...items], only, 3).map((row) => row.id)).toEqual([1, 2, 3])
  })

  it("returns nothing when the feed holds only this article", () => {
    expect(relatedArticles([open], open, 3)).toEqual([])
  })
})
