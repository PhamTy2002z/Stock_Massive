import { describe, expect, it } from "vitest"

import type { FeedNewsItem } from "./api"
import {
  articleFacet,
  articleKey,
  findArticle,
  formatPublishedDate,
  formatStreamDate,
  parsePublishedAt,
  partitionFeed,
  relatedArticles,
} from "./news"

/**
 * One press item, with only the fields the helpers actually read spelled out.
 *
 * `symbol: null` is the default because that is what the press feed looks like:
 * a CafeF article is about a story and names no ticker. The disclosure shape —
 * a symbol and no category — is spelled out where a test needs it.
 */
function item(overrides: Partial<FeedNewsItem> & { id: string }): FeedNewsItem {
  return {
    title: `Tin ${overrides.id}`,
    source: "CafeF",
    published_at: "2026-06-15T17:09:00+07:00",
    summary: null,
    content: null,
    url: null,
    image_url: null,
    category: "moi-nhat",
    symbol: null,
    price: null,
    price_change_pct: null,
    ...overrides,
  }
}

/** A feed of `count` items on the same facet, in the order the API returns them. */
function feed(count: number): FeedNewsItem[] {
  return Array.from({ length: count }, (_, index) => item({ id: String(index) }))
}

describe("articleKey", () => {
  it("names a press article by its facet and id", () => {
    expect(articleKey(item({ id: "18826", category: "chung-khoan" }))).toBe("chung-khoan:18826")
  })

  it("names a disclosure by its symbol, which takes precedence over the facet", () => {
    expect(articleKey(item({ id: "7", symbol: "VCB", category: "moi-nhat" }))).toBe("VCB:7")
  })

  it("falls back to a fixed namespace when the item names neither", () => {
    expect(articleKey(item({ id: "7", category: null }))).toBe("feed:7")
  })

  it("separates the same id under two facets, so two sources cannot collide", () => {
    expect(articleKey(item({ id: "7", category: "vi-mo" }))).not.toBe(
      articleKey(item({ id: "7", category: "quoc-te" })),
    )
    expect(articleKey(item({ id: "7", category: "vi-mo" }))).not.toBe(
      articleKey(item({ id: "7", symbol: "VCB" })),
    )
  })
})

describe("articleFacet", () => {
  it("reads back the namespace articleKey wrote", () => {
    const article = item({ id: "18826", category: "chung-khoan" })
    expect(articleFacet(articleKey(article))).toBe("chung-khoan")
  })

  it("keeps the whole string when there is no namespace to split off", () => {
    expect(articleFacet("moi-nhat")).toBe("moi-nhat")
  })
})

describe("findArticle", () => {
  const items = [
    item({ id: "1", category: "chung-khoan" }),
    item({ id: "2", category: "vi-mo" }),
  ]

  it("returns the article a key points at", () => {
    expect(findArticle(items, "vi-mo:2")?.id).toBe("2")
  })

  it("returns null for a key the feed no longer holds", () => {
    expect(findArticle(items, "chung-khoan:999")).toBeNull()
  })

  it("returns null when the id matches under another facet", () => {
    expect(findArticle(items, "vi-mo:1")).toBeNull()
  })

  it("returns null for no key at all", () => {
    expect(findArticle(items, null)).toBeNull()
  })

  it("returns null on an empty feed", () => {
    expect(findArticle([], "chung-khoan:1")).toBeNull()
  })
})

describe("parsePublishedAt", () => {
  // Shape one: CafeF, an ISO instant carrying its own offset.
  it("trusts the offset an ISO timestamp states", () => {
    expect(parsePublishedAt("2026-08-17T19:59:00+07:00")?.toISOString()).toBe(
      "2026-08-17T12:59:00.000Z",
    )
  })

  it("reads an offset that is not Vietnam's as the offset it says", () => {
    expect(parsePublishedAt("2026-08-17T19:59:00+00:00")?.toISOString()).toBe(
      "2026-08-17T19:59:00.000Z",
    )
    expect(parsePublishedAt("2026-08-17T19:59:00Z")?.toISOString()).toBe(
      "2026-08-17T19:59:00.000Z",
    )
  })

  it("accepts an ISO timestamp without seconds, and one with fractions", () => {
    expect(parsePublishedAt("2026-08-17T19:59+07:00")?.toISOString()).toBe(
      "2026-08-17T12:59:00.000Z",
    )
    expect(parsePublishedAt("2026-08-17T19:59:00.250+07:00")?.toISOString()).toBe(
      "2026-08-17T12:59:00.250Z",
    )
  })

  it("rejects an ISO timestamp on a day that does not exist", () => {
    expect(parsePublishedAt("2026-02-30T09:30:00+07:00")).toBeNull()
    expect(parsePublishedAt("2026-13-01T09:30:00+07:00")).toBeNull()
  })

  // Shape two: VCI, a bare wall clock that means Ho Chi Minh time.
  it("reads a zoneless wall clock as Ho Chi Minh time", () => {
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

  it("reads an offset timestamp back out in Ho Chi Minh time", () => {
    expect(formatPublishedDate("2026-06-15T17:09:00+07:00")).toBe("Thứ Hai, 15/6/2026, 17:09")
    // Same instant, stated from UTC: still the Vietnamese wall clock on screen.
    expect(formatPublishedDate("2026-06-15T10:09:00Z")).toBe("Thứ Hai, 15/6/2026, 17:09")
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
    expect(formatStreamDate("2026-06-17T08:00:00+07:00")).toBe("17/06/2026")
  })

  it("falls back to the raw string", () => {
    expect(formatStreamDate("không rõ")).toBe("không rõ")
  })
})

describe("partitionFeed", () => {
  it("cuts a full feed into hero, spotlight, grid and stream", () => {
    const parts = partitionFeed(feed(12))

    expect(parts.hero?.id).toBe("0")
    expect(parts.spotlight.map((row) => row.id)).toEqual(["1", "2"])
    expect(parts.grid.map((row) => row.id)).toEqual(["3", "4", "5", "6"])
    expect(parts.stream.map((row) => row.id)).toEqual(["7", "8", "9", "10", "11"])
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

    expect(parts.hero?.id).toBe("0")
    expect(parts.spotlight.map((row) => row.id)).toEqual(["1"])
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

describe("relatedArticles", () => {
  const open = item({ id: "1", category: "chung-khoan" })
  const items = [
    open,
    item({ id: "2", category: "vi-mo" }),
    item({ id: "3", category: "chung-khoan" }),
    item({ id: "4", category: "quoc-te" }),
    item({ id: "5", category: "chung-khoan" }),
  ]

  it("puts the same category first and never the article itself", () => {
    expect(relatedArticles(items, open, 3).map((row) => row.id)).toEqual(["3", "5", "2"])
  })

  it("pads with the newest others when the category has nothing else", () => {
    const only = item({ id: "9", category: "bat-dong-san" })
    expect(relatedArticles([only, ...items], only, 3).map((row) => row.id)).toEqual([
      "1",
      "2",
      "3",
    ])
  })

  it("groups the items that name no category together, rather than with everything", () => {
    const orphan = item({ id: "9", category: null })
    const rows = relatedArticles([orphan, item({ id: "8", category: null }), ...items], orphan, 3)
    expect(rows.map((row) => row.id)).toEqual(["8", "1", "2"])
  })

  it("returns nothing when the feed holds only this article", () => {
    expect(relatedArticles([open], open, 3)).toEqual([])
  })
})
