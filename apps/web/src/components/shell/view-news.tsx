"use client"

import { useMemo, useState, type ReactNode } from "react"
import { ArrowLeft, ExternalLink, PanelRight } from "lucide-react"

import { useMarketIndices } from "@/hooks/use-market-indices"
import { useNewsFeed } from "@/hooks/use-news"
import type { FeedNewsItem } from "@/lib/api"
import {
  articleKey,
  findArticle,
  formatPublishedDate,
  formatStreamDate,
  partitionFeed,
  relatedArticles,
  topSymbols,
} from "@/lib/news"
import { cn } from "@/lib/utils"

import { Card, deltaClass, Eyebrow, Figure, PanelCard, QuietLine, signedPercent } from "./primitives"
import { useShell } from "./shell-state"

/** As many pills as the row can hold before it starts scrolling in earnest. */
const MAX_PILLS = 6

/**
 * The news surface: a feed of what was published, and one article at a time.
 *
 * Both are one view rather than two, because the article is not a destination —
 * it is the feed with one item opened, and the reader goes back to the row they
 * came from. Which article is open lives in the shell's reducer for that reason;
 * the filter does not, because a pill is a way of looking at this list and means
 * nothing once the reader has left it.
 *
 * The feed is the only source of articles on this screen. The reader clicked a
 * row that was in it, so the article is in it too — and when a refetch has
 * dropped that row, saying so is the honest answer rather than fetching the one
 * item back and pretending the list never moved.
 */
export function NewsView() {
  const { state } = useShell()
  const feed = useNewsFeed()
  const [filter, setFilter] = useState<string | null>(null)

  const items = feed.data?.items ?? []

  if (state.newsArticle !== null) {
    return (
      <ArticleScreen
        article={findArticle(items, state.newsArticle)}
        items={items}
        pending={feed.isPending}
        isError={feed.isError}
        onRetry={() => void feed.refetch()}
      />
    )
  }

  return (
    <FeedScreen
      items={items}
      filter={filter}
      onFilter={setFilter}
      pending={feed.isPending}
      isError={feed.isError}
      onRetry={() => void feed.refetch()}
    />
  )
}

// ---------------------------------------------------------------------------
// Feed

function FeedScreen({
  items,
  filter,
  onFilter,
  pending,
  isError,
  onRetry,
}: {
  items: FeedNewsItem[]
  filter: string | null
  onFilter: (symbol: string | null) => void
  pending: boolean
  isError: boolean
  onRetry: () => void
}) {
  const symbols = useMemo(() => topSymbols(items, MAX_PILLS), [items])
  // Filtering here rather than in the query: the feed is one request the whole
  // screen shares, and asking the API again per pill would spend the provider's
  // quota to re-answer a question already on the client.
  const visible = useMemo(
    () => (filter === null ? items : items.filter((item) => item.symbol === filter)),
    [items, filter],
  )
  const blocks = useMemo(() => partitionFeed(visible), [visible])

  return (
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-1.5">
      <div className="mx-auto grid max-w-[1180px] gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          {symbols.length > 0 && (
            <PillRow symbols={symbols} filter={filter} onFilter={onFilter} />
          )}

          {isError ? (
            <Card className="mt-3.5">
              <p className="text-row text-ink-2">Chưa đọc được tin tức.</p>
              <p className="mt-1 text-meta leading-relaxed text-ink-5">
                Nguồn tin không trả lời. Bảng giá và hội thoại vẫn hoạt động bình thường.
              </p>
              <RetryButton onClick={onRetry} className="mt-3" />
            </Card>
          ) : pending ? (
            <FeedSkeleton />
          ) : visible.length === 0 ? (
            <QuietLine>
              {filter === null
                ? "Chưa có tin tức nào trong bảng tin."
                : `Chưa có tin nào về ${filter}.`}
            </QuietLine>
          ) : (
            <>
              {blocks.hero && <HeroBlock hero={blocks.hero} spotlight={blocks.spotlight} />}

              {blocks.grid.length > 0 && (
                <section aria-label="Tin đáng chú ý" className="mt-6 grid grid-cols-2 gap-5 lg:grid-cols-4">
                  {blocks.grid.map((item) => (
                    <SmallCard key={articleKey(item)} item={item} />
                  ))}
                </section>
              )}

              {blocks.stream.length > 0 && <Stream items={blocks.stream} />}
            </>
          )}
        </div>

        <Rail items={items} onFilter={onFilter} />
      </div>
    </div>
  )
}

/** "Mới nhất", then the symbols the feed is made of. */
function PillRow({
  symbols,
  filter,
  onFilter,
}: {
  symbols: string[]
  filter: string | null
  onFilter: (symbol: string | null) => void
}) {
  return (
    // The row scrolls rather than wraps: a second line of pills reads as a
    // second control, and the first pill must stay where the eye left it.
    <div
      role="group"
      aria-label="Lọc bảng tin theo mã"
      className="scrollbar-thin -mx-1 flex gap-1 overflow-x-auto px-1 pb-0.5"
    >
      <Pill active={filter === null} onClick={() => onFilter(null)}>
        Mới nhất
      </Pill>
      {symbols.map((symbol) => (
        <Pill key={symbol} active={filter === symbol} onClick={() => onFilter(symbol)}>
          <Figure>{symbol}</Figure>
        </Pill>
      ))}
    </div>
  )
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "shrink-0 whitespace-nowrap rounded-pill px-3 py-1.5 text-control transition-colors",
        active ? "bg-accent text-foreground" : "text-ink-3 hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

/**
 * The top of the feed: one article at display size, two beside it.
 *
 * The spotlight column is fixed at 264px and the hero takes what is left, so the
 * hero's image is always the widest thing on the screen. Below `md` the whole
 * block stacks, which puts the hero first — the order it is read in.
 */
function HeroBlock({ hero, spotlight }: { hero: FeedNewsItem; spotlight: FeedNewsItem[] }) {
  return (
    <section aria-label="Tin nổi bật" className="mt-3.5 grid gap-5 md:grid-cols-[264px_minmax(0,1fr)]">
      <div className="order-2 grid content-start gap-5 md:order-1">
        {spotlight.map((item) => (
          <SmallCard key={articleKey(item)} item={item} />
        ))}
      </div>

      <ArticleLink item={hero} className="order-1 min-w-0 md:order-2">
        <NewsImage item={hero} scale="lg" className="aspect-[16/9] w-full rounded-card" />
        <h2 className="mt-3 text-balance font-serif text-[1.9rem] leading-[1.15] text-ink-display">
          {hero.title}
        </h2>
        {hero.summary && (
          <p className="mt-2 line-clamp-2 text-row leading-relaxed text-ink-3">{hero.summary}</p>
        )}
        <SourceLine item={hero} withDate className="mt-2.5" />
      </ArticleLink>
    </section>
  )
}

/** The anatomy every card on this screen repeats: image, headline, identity. */
function SmallCard({ item }: { item: FeedNewsItem }) {
  return (
    <ArticleLink item={item} className="min-w-0">
      <NewsImage item={item} className="aspect-[16/9] w-full rounded-xl" />
      <h3 className="mt-2 line-clamp-3 text-row leading-snug text-ink-1">{item.title}</h3>
      <SourceLine item={item} className="mt-1.5" />
    </ArticleLink>
  )
}

/**
 * The rest of the feed, as dated rows.
 *
 * The date is printed once per day rather than once per row: the gutter is there
 * to tell the reader when they crossed into yesterday, and repeating it on every
 * row turns the column into noise. The gutter keeps its width on the rows that
 * say nothing, or the headlines would step left under each heading.
 */
function Stream({ items }: { items: FeedNewsItem[] }) {
  let previous = ""

  return (
    <section aria-label="Tin theo ngày" className="mt-7">
      {items.map((item) => {
        const day = formatStreamDate(item.published_at)
        const heads = day !== previous
        previous = day

        return (
          <ArticleLink
            key={articleKey(item)}
            item={item}
            className="flex gap-4 border-t border-border py-4"
          >
            <Figure className="w-[84px] shrink-0 text-meta text-ink-6">{heads ? day : ""}</Figure>
            <div className="min-w-0 flex-1">
              <h3 className="line-clamp-2 text-[1.05rem] font-medium leading-snug text-ink-1">
                {item.title}
              </h3>
              {item.summary && (
                <p className="mt-1.5 line-clamp-2 text-meta leading-relaxed text-ink-4">
                  {item.summary}
                </p>
              )}
              <SourceLine item={item} className="mt-2" />
            </div>
            <NewsImage
              item={item}
              scale="sm"
              className="h-20 w-32 shrink-0 rounded-lg object-cover"
            />
          </ArticleLink>
        )
      })}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Rail

/**
 * The right-hand rail: the session, the newest headlines, and the symbols.
 *
 * Hidden below `xl` rather than stacked under the feed. Everything in it is a
 * shortcut into the column beside it, and a shortcut that sits below the whole
 * feed is a shortcut nobody reaches.
 */
function Rail({
  items,
  onFilter,
}: {
  items: FeedNewsItem[]
  onFilter: (symbol: string | null) => void
}) {
  const { dispatch } = useShell()
  const symbols = useMemo(() => topSymbols(items, MAX_PILLS), [items])
  const newest = items.slice(0, 5)

  return (
    <aside aria-label="Bên lề bảng tin" className="sticky top-0 hidden grid-cols-fit content-start gap-3.5 self-start xl:grid">
      <MarketWidget />

      {newest.length > 0 && (
        <Card className="min-w-0">
          <Eyebrow>Mới cập nhật</Eyebrow>
          <div className="mt-2 grid grid-cols-fit">
            {newest.map((item) => (
              <button
                key={articleKey(item)}
                type="button"
                onClick={() => dispatch({ type: "news-article", article: articleKey(item) })}
                className="flex items-start gap-2.5 rounded-lg border-t border-hairline py-2.5 text-left transition-colors first:border-t-0 hover:bg-foreground/[0.035]"
              >
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 block text-control leading-snug text-ink-2">
                    {item.title}
                  </span>
                  <Figure className="mt-1 block text-micro text-ink-6">{item.symbol}</Figure>
                </span>
                <NewsImage
                  item={item}
                  scale="sm"
                  className="size-14 shrink-0 rounded-lg object-cover"
                />
              </button>
            ))}
          </div>
        </Card>
      )}

      {symbols.length > 0 && (
        <Card className="min-w-0">
          <Eyebrow>Theo mã</Eyebrow>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {symbols.map((symbol) => (
              <button
                key={symbol}
                type="button"
                onClick={() => onFilter(symbol)}
                className="rounded-pill border border-border px-2.5 py-1 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
              >
                <Figure>{symbol}</Figure>
              </button>
            ))}
          </div>
        </Card>
      )}
    </aside>
  )
}

/**
 * What the market is doing while the reader reads.
 *
 * The reference puts the weather here. This is a trading surface, so the index
 * is the weather — and the headline index is stated at figure size because it is
 * the one number that changes how every headline under it reads.
 */
function MarketWidget() {
  const indices = useMarketIndices()
  const rows = indices.data ?? []
  const [headline, ...rest] = rows

  return (
    <PanelCard className="min-w-0">
      {headline ? (
        <>
          <div className="text-micro font-semibold tracking-[0.06em] text-ink-4">
            {headline.name}
          </div>
          <Figure
            className={cn(
              "mt-1 block text-[1.6rem] font-semibold tracking-[-0.025em]",
              deltaClass(headline.changePercent),
            )}
          >
            {headline.value.toLocaleString("vi-VN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </Figure>
          <Figure className={cn("block text-meta", deltaClass(headline.changePercent))}>
            {headline.changePercent >= 0 ? "▲" : "▼"}{" "}
            {Math.abs(headline.change).toLocaleString("vi-VN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}{" "}
            ({signedPercent(headline.changePercent)})
          </Figure>

          <div className="mt-2.5 grid grid-cols-fit">
            {rest.map((index) => (
              <div
                key={index.symbol}
                className="flex items-baseline gap-2 border-t border-hairline py-1.5 text-meta"
              >
                <span className="min-w-0 flex-1 truncate text-ink-5">{index.name}</span>
                <Figure className="text-ink-2">
                  {index.value.toLocaleString("vi-VN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Figure>
                <Figure className={cn("w-[62px] shrink-0 text-right", deltaClass(index.changePercent))}>
                  {signedPercent(index.changePercent)}
                </Figure>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-meta text-ink-6">
          {indices.isPending ? "Đang tải chỉ số…" : "Chưa có dữ liệu chỉ số."}
        </p>
      )}
    </PanelCard>
  )
}

// ---------------------------------------------------------------------------
// Article

/**
 * One article, read in place.
 *
 * A reading column of 720px and a serif face, because this is the one surface in
 * the product that is prose rather than figures. The body arrives as plain text
 * with the source's own paragraph breaks in it, so the breaks are what it is set
 * from — a single block would be a wall, and re-inferring paragraphs from
 * sentence length would be inventing structure the source did not publish.
 */
function ArticleScreen({
  article,
  items,
  pending,
  isError,
  onRetry,
}: {
  article: FeedNewsItem | null
  items: FeedNewsItem[]
  pending: boolean
  isError: boolean
  onRetry: () => void
}) {
  const { dispatch } = useShell()
  const back = () => dispatch({ type: "news-article", article: null })

  if (article === null) {
    return (
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-1.5">
        <div className="mx-auto w-full max-w-[720px] py-10">
          {/* The article is looked up in the feed, so a feed that did not load
              is a different fact from an article that has scrolled out of it.
              Saying "no longer in the feed" when the request failed would send
              the reader looking for a row that may still be there. */}
          {isError ? (
            <>
              <p className="text-row text-ink-2">Chưa đọc được bài viết.</p>
              <p className="mt-1 text-meta text-ink-5">
                Bảng tin không tải được nên chưa mở được bài này.
              </p>
              <RetryButton onClick={onRetry} className="mt-3" />
            </>
          ) : (
            <QuietLine>
              {pending ? "Đang mở bài viết…" : "Bài viết không còn trong bảng tin."}
            </QuietLine>
          )}
          <BackButton onClick={back} className="mt-2" />
        </div>
      </div>
    )
  }

  const related = relatedArticles(items, article, 3)
  const paragraphs = bodyParagraphs(article)

  return (
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
      {/* Sticky inside the view rather than in the app's own header: the way
          back belongs to the article, and it must stay reachable from the
          bottom of a body several screens long. */}
      <div className="sticky top-0 z-[5] flex items-center gap-2 border-b border-border bg-background/95 px-5 py-2.5 backdrop-blur">
        <BackButton onClick={back} />

        <div className="ml-auto flex items-center gap-2">
          {article.url && (
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[9px] border border-border px-2.5 py-1.5 text-meta text-ink-4 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
            >
              <ExternalLink className="size-[15px]" strokeWidth={1.6} />
              Bài gốc
            </a>
          )}
          <button
            type="button"
            onClick={() => dispatch({ type: "open-inspector", tab: "news" })}
            className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[9px] border border-border px-2.5 py-1.5 text-meta text-ink-4 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
          >
            <PanelRight className="size-[15px]" strokeWidth={1.6} />
            Nguồn
          </button>
        </div>
      </div>

      <article className="mx-auto w-full max-w-[720px] px-5 py-10">
        <h1 className="text-balance font-serif text-[2.1rem] leading-[1.18] text-ink-display">
          {article.title}
        </h1>

        <div className="mt-3.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-meta text-ink-5">{formatPublishedDate(article.published_at)}</span>
          <SourceLine item={article} />
          <button
            type="button"
            onClick={() =>
              dispatch({
                type: "select-symbol",
                selected: { symbol: article.symbol, name: article.symbol, exchange: "—" },
                open: true,
              })
            }
            className="rounded-pill border border-border px-2.5 py-1 text-micro text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
          >
            <Figure>{article.symbol}</Figure>
          </button>
        </div>

        {article.summary && (
          <p className="mt-5 font-serif text-[1.12rem] leading-relaxed text-ink-2">
            {article.summary}
          </p>
        )}

        <NewsImage item={article} scale="lg" className="mt-6 aspect-[16/9] w-full rounded-card" />

        {paragraphs.length > 0 ? (
          <div className="mt-6 grid gap-4 font-serif text-[1.05rem] leading-[1.75] text-ink-2">
            {paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        ) : (
          <div className="mt-6">
            <QuietLine>Nguồn tin chỉ cung cấp tiêu đề cho bài này.</QuietLine>
            {article.url && (
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mx-2.5 inline-flex items-center gap-1.5 text-control text-primary hover:underline"
              >
                <ExternalLink className="size-[15px]" strokeWidth={1.6} />
                Đọc bài gốc tại {article.source}
              </a>
            )}
          </div>
        )}

        {related.length > 0 && (
          <section aria-label="Bài liên quan" className="mt-10 border-t border-border pt-6">
            <Eyebrow>Bài liên quan</Eyebrow>
            <div className="mt-3 grid grid-cols-3 gap-3.5">
              {related.map((item) => (
                <button
                  key={articleKey(item)}
                  type="button"
                  onClick={() => dispatch({ type: "news-article", article: articleKey(item) })}
                  className="min-w-0 rounded-card border border-border p-2.5 text-left transition-colors hover:bg-foreground/[0.035]"
                >
                  <NewsImage item={item} className="aspect-[16/9] w-full rounded-lg" />
                  <span className="mt-2 line-clamp-2 block text-control leading-snug text-ink-2">
                    {item.title}
                  </span>
                  <Figure className="mt-1.5 block text-micro text-ink-6">
                    {formatStreamDate(item.published_at)}
                  </Figure>
                </button>
              ))}
            </div>
          </section>
        )}
      </article>
    </div>
  )
}

/** Re-asks for the feed. Both screens read the same query, so both offer it. */
function RetryButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-[10px] bg-primary px-3.5 py-2 text-control font-medium text-primary-foreground transition-[filter] hover:brightness-110",
        className,
      )}
    >
      Thử lại
    </button>
  )
}

function BackButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[9px] px-2 py-1.5 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground",
        className,
      )}
    >
      <ArrowLeft className="size-4" strokeWidth={1.7} />
      Trở về tin tức
    </button>
  )
}

/**
 * The body, or the summary standing in for it.
 *
 * Empty lines are dropped rather than kept as blank paragraphs: the providers
 * pad their text with them, and a gap the source did not intend reads as a
 * missing image.
 */
function bodyParagraphs(item: FeedNewsItem): string[] {
  const text = item.content ?? item.summary ?? ""
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

// ---------------------------------------------------------------------------
// Shared pieces

/**
 * Where an article came from: the source, the symbol, and when.
 *
 * The identity unit of this whole screen — every card, row and rail entry ends
 * with one, so a headline is never read without knowing who published it. The
 * date is opt-in because most of the surfaces that draw this already state it
 * somewhere the eye reaches first.
 */
export function SourceLine({
  item,
  withDate = false,
  className,
}: {
  item: { source: string; symbol?: string; published_at: string }
  withDate?: boolean
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5 text-micro text-ink-5", className)}>
      <span className="rounded-pill bg-foreground/[0.06] px-1.5 py-0.5 lowercase">
        {item.source}
      </span>
      {item.symbol && <Figure>{item.symbol}</Figure>}
      {withDate && item.published_at.trim() !== "" && (
        <span>· {formatStreamDate(item.published_at)}</span>
      )}
    </div>
  )
}

/** How large the symbol is drawn when there is no image to draw. */
const FALLBACK_FIGURE = {
  sm: "text-[0.95rem]",
  md: "text-[1.4rem]",
  lg: "text-[2.4rem]",
} as const

/**
 * An article's picture, or the symbol standing in for it.
 *
 * A plain `img`: the hosts are the publishers' own and unknown ahead of time, so
 * `next/image` would need every one of them allow-listed in the config and would
 * fail closed on the next source the provider adds. The fallback covers both a
 * missing URL and a URL that turns out not to resolve — the reader gets a plate
 * with the symbol on it either way, and never a broken-image glyph in the middle
 * of a card.
 */
function NewsImage({
  item,
  className,
  scale = "md",
}: {
  item: FeedNewsItem
  className?: string
  scale?: keyof typeof FALLBACK_FIGURE
}) {
  const [failed, setFailed] = useState(false)

  if (item.image_url === null || failed) {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "flex items-center justify-center overflow-hidden bg-surface-sunken",
          className,
        )}
      >
        <Figure className={cn("font-serif text-ink-6", FALLBACK_FIGURE[scale])}>
          {item.symbol}
        </Figure>
      </div>
    )
  }

  return (
    <img
      src={item.image_url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn("bg-surface-sunken object-cover", className)}
    />
  )
}

/** One article's whole card as a single control, headline included. */
function ArticleLink({
  item,
  className,
  children,
}: {
  item: FeedNewsItem
  className?: string
  children: ReactNode
}) {
  const { dispatch } = useShell()

  return (
    <button
      type="button"
      onClick={() => dispatch({ type: "news-article", article: articleKey(item) })}
      className={cn(
        "group/news w-full text-left",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      {children}
    </button>
  )
}

/**
 * The feed's own shape while it is still arriving.
 *
 * The blocks are drawn at the sizes the real ones take, so the screen does not
 * reflow under the reader's cursor when the headlines land.
 */
function FeedSkeleton() {
  return (
    <div className="mt-3.5" aria-busy="true">
      <span className="sr-only">Đang tải bảng tin</span>
      <div className="grid gap-5 md:grid-cols-[264px_minmax(0,1fr)]">
        <div className="grid content-start gap-5">
          {[0, 1].map((slot) => (
            <Card key={`spotlight-skeleton-${slot}`} className="h-[210px] animate-pulse" >
              <span className="sr-only">Đang tải tin</span>
            </Card>
          ))}
        </div>
        <Card className="h-[440px] animate-pulse">
          <span className="sr-only">Đang tải tin nổi bật</span>
        </Card>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-5 lg:grid-cols-4">
        {[0, 1, 2, 3].map((slot) => (
          <Card key={`grid-skeleton-${slot}`} className="h-[190px] animate-pulse">
            <span className="sr-only">Đang tải tin</span>
          </Card>
        ))}
      </div>
    </div>
  )
}
