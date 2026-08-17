import type { FeedNewsItem } from "./api"

/**
 * Everything the news surface decides about a feed, away from the components.
 *
 * The feed arrives as one flat, newest-first list and is drawn as five different
 * shapes — a hero, two spotlights, a row of four, a dated stream, a rail. Which
 * item belongs to which shape is arithmetic on that list, and arithmetic that a
 * component does inline is arithmetic nothing can test. So it lives here, pure,
 * and the view only lays out what it is handed.
 */

/** How an article is named in shell state: stable across a refetch, unlike an index. */
export function articleKey(item: FeedNewsItem): string {
  return `${item.symbol}:${item.id}`
}

/**
 * The article a key points at, or `null` when the feed no longer holds it.
 *
 * A refresh can drop the article that is open — it is a window over a moving
 * list, not a resource — and the reader is told that rather than shown a blank
 * page.
 */
export function findArticle(items: FeedNewsItem[], key: string | null): FeedNewsItem | null {
  if (key === null) return null
  return items.find((item) => articleKey(item) === key) ?? null
}

/**
 * Vietnam is UTC+7 all year and has been since 1975, so the offset is a constant
 * rather than a lookup. It is what turns the provider's wall-clock string into
 * an instant: without it the parse would mean "07:00 wherever this browser is",
 * and the same article would carry two different timestamps on two machines.
 */
const HO_CHI_MINH_OFFSET_MS = 7 * 60 * 60 * 1000

const TIME_ZONE = "Asia/Ho_Chi_Minh"

/** `"YYYY-MM-DD HH:mm"`, and nothing else. `T` between date and time is tolerated. */
const PUBLISHED_AT = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/

/**
 * The instant an article was published, or `null` for anything unparseable.
 *
 * Built from the captured parts rather than handed to `new Date(string)`: the
 * string has no zone in it, and the two engines that accept it disagree about
 * whether that means UTC or local time.
 */
export function parsePublishedAt(value: string): Date | null {
  const match = PUBLISHED_AT.exec(value.trim())
  if (match === null) return null

  const [, year, month, day, hour, minute] = match
  const utc = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
  )
  const moment = new Date(utc - HO_CHI_MINH_OFFSET_MS)
  if (Number.isNaN(moment.getTime())) return null
  // `Date.UTC` rolls a 13th month over into the next year rather than refusing
  // it, so the round trip is what actually rejects an impossible date.
  const parts = ISO_PARTS.formatToParts(moment)
  const field = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ""
  const roundTripped =
    field("year") === year &&
    field("month") === month &&
    field("day") === day &&
    field("hour") === hour &&
    field("minute") === minute
  return roundTripped ? moment : null
}

/** The parse's own mirror: the same fields, in the same zone, back out as text. */
const ISO_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

const LONG_DATE = new Intl.DateTimeFormat("vi-VN", {
  timeZone: TIME_ZONE,
  weekday: "long",
  day: "numeric",
  month: "numeric",
  year: "numeric",
})

const LONG_TIME = new Intl.DateTimeFormat("vi-VN", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

const SHORT_DATE = new Intl.DateTimeFormat("vi-VN", {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
})

/**
 * "Thứ Hai, 15/6/2026, 17:09" — the byline under an article's title.
 *
 * Two formatters joined rather than one: `vi-VN` puts the clock in front of the
 * date when asked for both at once, which reads as a log line rather than as a
 * date. An unparseable value is shown verbatim — the provider printed something,
 * and a dash would hide information the reader could still use.
 */
export function formatPublishedDate(value: string): string {
  const moment = parsePublishedAt(value)
  if (moment === null) return value
  return `${LONG_DATE.format(moment)}, ${LONG_TIME.format(moment)}`
}

/** "15/06/2026" — the stream's left gutter, where every row must align. */
export function formatStreamDate(value: string): string {
  const moment = parsePublishedAt(value)
  if (moment === null) return value
  return SHORT_DATE.format(moment)
}

/** How many items each block of the feed takes, in the order they are drawn. */
const SPOTLIGHT_END = 3
const GRID_END = 7

export interface FeedPartition {
  /** The one article the screen opens on, or `null` on an empty feed. */
  hero: FeedNewsItem | null
  /** The two stacked beside it. */
  spotlight: FeedNewsItem[]
  /** The row of four under both. */
  grid: FeedNewsItem[]
  /** Everything else, as dated rows. */
  stream: FeedNewsItem[]
}

/**
 * The feed cut into the blocks the screen draws.
 *
 * Every block is a slice, so a feed of three items fills the hero and the
 * spotlight and leaves the rest empty rather than repeating an article in two
 * places — the same headline in two shapes reads as a bug in the feed.
 */
export function partitionFeed(items: FeedNewsItem[]): FeedPartition {
  return {
    hero: items[0] ?? null,
    spotlight: items.slice(1, SPOTLIGHT_END),
    grid: items.slice(SPOTLIGHT_END, GRID_END),
    stream: items.slice(GRID_END),
  }
}

/**
 * The symbols the feed is actually made of, loudest first.
 *
 * Ordered by how many articles each contributed, then alphabetically so a tie
 * does not reshuffle the pill row between two refetches of the same feed.
 */
export function topSymbols(items: FeedNewsItem[], max: number): string[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    counts.set(item.symbol, (counts.get(item.symbol) ?? 0) + 1)
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, max)
    .map(([symbol]) => symbol)
}

/**
 * What to read after this one: the same company first, then simply the newest.
 *
 * Padding with unrelated articles rather than showing one card is deliberate.
 * The block's promise is "there is more", and a symbol the provider only covered
 * once would otherwise end the reading there.
 */
export function relatedArticles(
  items: FeedNewsItem[],
  article: FeedNewsItem,
  max: number,
): FeedNewsItem[] {
  const openKey = articleKey(article)
  const others = items.filter((item) => articleKey(item) !== openKey)
  const sameSymbol = others.filter((item) => item.symbol === article.symbol)
  const rest = others.filter((item) => item.symbol !== article.symbol)
  return [...sameSymbol, ...rest].slice(0, max)
}
