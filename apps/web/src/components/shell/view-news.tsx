"use client"

import { useMemo, useState, type ReactNode } from "react"
import {
  ArrowLeft,
  Check,
  ChevronRight,
  ExternalLink,
  Facebook,
  Link2,
  Linkedin,
  PanelRight,
  Twitter,
} from "lucide-react"

import { useMarketIndices } from "@/hooks/use-market-indices"
import {
  useCompanyNews,
  useNewsArticle,
  useNewsCategories,
  useNewsFeed,
} from "@/hooks/use-news"
import type { ArticleBlock, FeedNewsItem, NewsCategory } from "@/lib/api"
import {
  articleBody,
  articleKey,
  findArticle,
  formatPublishedDate,
  formatStreamDate,
  partitionFeed,
  relatedArticles,
} from "@/lib/news"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

import { Card, deltaClass, Figure, QuietLine, signedPercent } from "./primitives"
import { useShell } from "./shell-state"

/** The facet the screen opens on, and the one the API answers with by default. */
export const DEFAULT_CATEGORY = "moi-nhat"

/** How many of a company's disclosures the rail is willing to list. */
const MAX_DISCLOSURES = 5

/** How many dated rows the stream opens with, and how many each press adds. */
const STREAM_PAGE = 8

/**
 * The news surface: a feed of what the press published, and one article at a time.
 *
 * Both are one view rather than two, because the article is not a destination —
 * it is the feed with one item opened, and the reader goes back to the row they
 * came from. Which article is open lives in the shell's reducer for that reason;
 * the category does not, because a pill is a way of looking at this list and
 * means nothing once the reader has left it.
 *
 * The feed is the only source of articles on this screen. The reader clicked a
 * row that was in it, so the article is in it too — and when a refetch has
 * dropped that row, saying so is the honest answer rather than fetching the one
 * item back and pretending the list never moved.
 *
 * The body is the one thing the feed does not carry. CafeF's RSS has no
 * full-text element — no Vietnamese finance feed measured beside it does — so
 * the reading column fetches the article's own page when it opens, and only
 * then. The feed stays one request per facet; a headline nobody pressed costs
 * nothing. Every reading surface still ends at the original, because the body
 * we print is an extract of someone else's page and says so.
 *
 * The measurements below are the news design's own — 41px on the lead headline,
 * 26px on a stream row, a 344px rail — written as pixels rather than as the
 * shell's named steps because this surface is set to a spec of its own. The
 * *colours* are the shell's tokens throughout: the design's ground and ink
 * ladder are the ones already in `globals.css`, so naming them keeps the day
 * theme working rather than nailing the view to six night-only hexes.
 */
export function NewsView() {
  const { state } = useShell()
  // Local, not reducer state: a facet is a lens on this list, in the same way
  // the old symbol filter was, and there is nothing for another surface to read.
  const [category, setCategory] = useState<string>(DEFAULT_CATEGORY)
  const feed = useNewsFeed(category)
  const registry = useNewsCategories()

  const items = feed.data?.items ?? []
  // The registry first, so the pill row still stands when the feed refused; the
  // feed's own copy is the fallback for the reverse case.
  const categories = registry.data ?? feed.data?.categories ?? []

  if (state.newsArticle !== null) {
    return (
      <ArticleScreen
        article={findArticle(items, state.newsArticle)}
        items={items}
        categories={categories}
        pending={feed.isPending}
        isError={feed.isError}
        onRetry={() => void feed.refetch()}
      />
    )
  }

  return (
    <FeedScreen
      items={items}
      categories={categories}
      category={category}
      onCategory={setCategory}
      pending={feed.isPending}
      isError={feed.isError}
      onRetry={() => void feed.refetch()}
    />
  )
}

/** What a facet is called, or its slug when the registry has not arrived. */
function categoryLabel(categories: NewsCategory[], slug: string | null): string | null {
  if (slug === null) return null
  return categories.find((entry) => entry.slug === slug)?.label ?? slug
}

// ---------------------------------------------------------------------------
// Feed

function FeedScreen({
  items,
  categories,
  category,
  onCategory,
  pending,
  isError,
  onRetry,
}: {
  items: FeedNewsItem[]
  categories: NewsCategory[]
  category: string
  onCategory: (slug: string) => void
  pending: boolean
  isError: boolean
  onRetry: () => void
}) {
  const blocks = useMemo(() => partitionFeed(items), [items])

  return (
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
      {categories.length > 0 && (
        <TabBar categories={categories} category={category} onCategory={onCategory} />
      )}

      <div className="mx-auto grid max-w-[1560px] items-start gap-11 px-5 pb-20 pt-7 lg:px-8 xl:grid-cols-[minmax(0,1fr)_344px] xl:px-10">
        <div className="flex min-w-0 flex-col gap-[34px]">
          {isError ? (
            <Card>
              <p className="text-row text-ink-2">Chưa đọc được tin tức.</p>
              <p className="mt-1 text-meta leading-relaxed text-ink-5">
                Nguồn tin không trả lời. Bảng giá và hội thoại vẫn hoạt động bình thường.
              </p>
              <RetryButton onClick={onRetry} className="mt-3" />
            </Card>
          ) : pending ? (
            <FeedSkeleton />
          ) : items.length === 0 ? (
            <QuietLine>
              {category === DEFAULT_CATEGORY
                ? "Chưa có tin tức nào trong bảng tin."
                : `Chưa có tin nào trong chủ đề ${categoryLabel(categories, category)}.`}
            </QuietLine>
          ) : (
            <>
              {blocks.hero && (
                <HeroBlock
                  hero={blocks.hero}
                  spotlight={blocks.spotlight}
                  categories={categories}
                />
              )}

              {blocks.grid.length > 0 && (
                <>
                  <Rule />
                  <section
                    aria-label="Tin đáng chú ý"
                    className="grid grid-cols-2 gap-6 lg:grid-cols-4"
                  >
                    {blocks.grid.map((item) => (
                      <GridCard key={articleKey(item)} item={item} categories={categories} />
                    ))}
                  </section>
                </>
              )}

              {blocks.stream.length > 0 && (
                <>
                  <Rule />
                  <Stream items={blocks.stream} categories={categories} />
                </>
              )}
            </>
          )}
        </div>

        <Rail items={items} />
      </div>
    </div>
  )
}

/** The hairline the design cuts between two blocks of a different shape. */
function Rule() {
  return <div className="h-px bg-border" aria-hidden="true" />
}

/**
 * The facets the API offers, as the reader's way of narrowing the feed.
 *
 * Every pill is a different request, not a filter over one list: the press feed
 * is per-category upstream, so there is no single response holding all of them
 * to sift on the client.
 *
 * Sticky and full-bleed, over a blurred ground: the row is the one control the
 * whole feed has, and a reader four screens into the stream who wants a
 * different subject should not have to scroll back up to the top to change it.
 */
function TabBar({
  categories,
  category,
  onCategory,
}: {
  categories: NewsCategory[]
  category: string
  onCategory: (slug: string) => void
}) {
  return (
    <div className="sticky top-0 z-20 border-b border-hairline bg-background/[0.86] backdrop-blur-[14px]">
      {/* The row scrolls rather than wraps: a second line of pills reads as a
          second control, and the first pill must stay where the eye left it. */}
      <div
        role="group"
        aria-label="Lọc bảng tin theo chủ đề"
        className="scrollbar-thin mx-auto flex max-w-[1560px] gap-1.5 overflow-x-auto px-5 py-3.5 lg:px-8 xl:px-10"
      >
        {categories.map((entry) => (
          <Pill
            key={entry.slug}
            active={category === entry.slug}
            onClick={() => onCategory(entry.slug)}
          >
            {entry.label}
          </Pill>
        ))}
      </div>
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
        "shrink-0 whitespace-nowrap rounded-pill px-[18px] py-[9px] text-[14.5px] leading-none transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "bg-surface-sunken text-foreground"
          : "text-ink-5 hover:bg-surface-sunken/70 hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

/**
 * The top of the feed: one article at display size, two beside it.
 *
 * The spotlight column is fixed at 300px and the lead takes what is left, so the
 * lead's image is always the widest thing on the screen. Below `md` the whole
 * block stacks, which puts the lead first — the order it is read in.
 */
function HeroBlock({
  hero,
  spotlight,
  categories,
}: {
  hero: FeedNewsItem
  spotlight: FeedNewsItem[]
  categories: NewsCategory[]
}) {
  return (
    <section
      aria-label="Tin nổi bật"
      className="grid items-start gap-[30px] md:grid-cols-[300px_minmax(0,1fr)]"
    >
      <div className="order-2 flex flex-col gap-[26px] md:order-1">
        {spotlight.map((item) => (
          <SpotlightCard key={articleKey(item)} item={item} categories={categories} />
        ))}
      </div>

      <ArticleLink item={hero} className="order-1 flex min-w-0 flex-col gap-5 md:order-2">
        <NewsImage item={hero} scale="lg" className="aspect-[16/10] w-full rounded-xl" />
        <div className="flex flex-col gap-3.5">
          <h2 className="text-pretty font-serif text-[32px] font-normal leading-[1.12] tracking-[-0.02em] text-ink-display xl:text-[41px]">
            {hero.title}
          </h2>
          {hero.summary && (
            <p className="line-clamp-3 max-w-[62ch] text-pretty font-serif text-[19px] leading-[1.5] text-ink-5">
              {hero.summary}
            </p>
          )}
          <SourceLine item={hero} categories={categories} withDate className="pt-0.5" />
        </div>
      </ArticleLink>
    </section>
  )
}

/** The two beside the lead: a wide picture, a serif headline, an identity. */
function SpotlightCard({ item, categories }: { item: FeedNewsItem; categories: NewsCategory[] }) {
  return (
    <ArticleLink item={item} className="flex min-w-0 flex-col gap-3">
      <NewsImage item={item} className="aspect-[16/9] w-full rounded-[10px]" />
      <h3 className="line-clamp-3 text-pretty font-serif text-[21px] font-normal leading-[1.28] tracking-[-0.01em] text-ink-1">
        {item.title}
      </h3>
      <SourceLine item={item} categories={categories} />
    </ArticleLink>
  )
}

/** The row of four under both, a step down in every dimension. */
function GridCard({ item, categories }: { item: FeedNewsItem; categories: NewsCategory[] }) {
  return (
    <ArticleLink item={item} className="flex min-w-0 flex-col gap-3">
      <NewsImage item={item} className="aspect-[16/10] w-full rounded-[10px]" />
      <h3 className="line-clamp-3 text-pretty font-serif text-[19px] font-normal leading-[1.3] text-ink-1">
        {item.title}
      </h3>
      <SourceLine item={item} categories={categories} />
    </ArticleLink>
  )
}

/**
 * The rest of the feed, as dated rows.
 *
 * The date is printed on every row rather than once per day. A feed pulled at
 * one moment is mostly one day deep, so the per-day heading left a 96px gutter
 * empty down the whole column — the date read as a field that had failed rather
 * than as one deliberately not repeated.
 *
 * The stream reveals itself in pages rather than all at once. The API answers
 * with the whole facet in one response — there is no cursor to ask for more —
 * so "Xem thêm tin" is exactly what it looks like: more of the list already in
 * hand, and the button leaves once there is nothing left behind it.
 */
function Stream({ items, categories }: { items: FeedNewsItem[]; categories: NewsCategory[] }) {
  const [shown, setShown] = useState(STREAM_PAGE)
  const visible = items.slice(0, shown)

  return (
    <section aria-label="Tin theo ngày" className="flex flex-col">
      {visible.map((item) => (
        <ArticleLink
          key={articleKey(item)}
          item={item}
          className={cn(
            "grid grid-cols-[72px_minmax(0,1fr)] items-start gap-4 rounded-xl border-b border-hairline py-[26px] pr-4",
            "transition-colors hover:bg-foreground/[0.025]",
            "md:grid-cols-[96px_minmax(0,1fr)_232px] md:gap-7",
          )}
        >
          <Figure className="pl-4 pt-[5px] text-[12px] text-ink-6">
            {formatStreamDate(item.published_at)}
          </Figure>

          <div className="flex min-w-0 flex-col gap-[11px]">
            <h3 className="text-pretty font-serif text-[22px] font-normal leading-[1.24] tracking-[-0.01em] text-ink-1 xl:text-[26px]">
              {item.title}
            </h3>
            {item.summary && (
              <p className="line-clamp-2 max-w-[70ch] text-pretty font-serif text-[17px] leading-[1.5] text-ink-5">
                {item.summary}
              </p>
            )}
            <SourceLine item={item} categories={categories} className="pt-0.5" />
          </div>

          <NewsImage
            item={item}
            className="hidden aspect-[16/10] w-full rounded-[10px] md:block"
          />
        </ArticleLink>
      ))}

      {shown < items.length && (
        <button
          type="button"
          onClick={() => setShown((count) => count + STREAM_PAGE)}
          className={cn(
            "mt-[30px] self-center rounded-pill border border-input px-[26px] py-3 text-[14px] text-ink-3",
            "transition-colors hover:border-ink-6 hover:bg-surface-sunken hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          Xem thêm tin
        </button>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Rail

/**
 * The right-hand rail: the session, the newest headlines, and the filings.
 *
 * Hidden below `xl` rather than stacked under the feed. Everything in it is
 * context for the column beside it, and context that sits below the whole feed
 * is context nobody reaches. It sticks below the tab bar, which is the one thing
 * on this screen that outranks it.
 */
function Rail({ items }: { items: FeedNewsItem[] }) {
  const { state, dispatch } = useShell()
  const newest = items.slice(0, 5)

  return (
    <aside
      aria-label="Bên lề bảng tin"
      className="sticky top-[78px] hidden grid-cols-fit content-start gap-[34px] self-start xl:grid"
    >
      <MarketWidget />

      {newest.length > 0 && (
        <RailSection title="Bài viết mới nhất">
          {newest.map((item) => (
            <button
              key={articleKey(item)}
              type="button"
              onClick={() => dispatch({ type: "news-article", article: articleKey(item) })}
              className={cn(
                "-mx-2.5 grid grid-cols-[minmax(0,1fr)_64px] items-start gap-3.5 rounded-[10px] px-2.5 py-[13px] text-left",
                "transition-colors hover:bg-foreground/[0.03]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <span className="line-clamp-3 min-w-0 text-pretty font-serif text-[16.5px] leading-[1.35] text-ink-3">
                {item.title}
              </span>
              <NewsImage
                item={item}
                scale="sm"
                className="h-[52px] w-16 rounded-lg object-cover"
              />
            </button>
          ))}
        </RailSection>
      )}

      <DisclosureCard symbol={state.selected.symbol} />
    </aside>
  )
}

/** A block of the rail: a serif heading, then rows that bleed past its padding. */
function RailSection({
  title,
  note,
  children,
}: {
  title: string
  note?: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-label={title} className="min-w-0">
      <div className="mb-3.5 flex items-center justify-between gap-2">
        <h2 className="font-serif text-[20px] font-medium leading-tight text-ink-1">{title}</h2>
        <ChevronRight className="size-4 shrink-0 text-ink-6" strokeWidth={1.6} aria-hidden="true" />
      </div>
      {note}
      <div className="grid grid-cols-fit">{children}</div>
    </section>
  )
}

/**
 * The selected company's filings, next to but never mixed into the press feed.
 *
 * A second source with a second character: VCI publishes what a company was
 * obliged to announce, and publishes it as a title and a date and nothing else.
 * There is no body to open, so these are text rather than controls — a row that
 * looked clickable would promise a reading surface that cannot exist. The note
 * under the heading is there for the same reason: "tin" on this screen otherwise
 * means a press article, and these are not that.
 *
 * It stands where the reference put a most-read list. Nothing upstream counts
 * reads, and a ranked list of headlines nobody ranked would be decoration
 * wearing the clothes of data; the filings are a real second feed and take the
 * slot honestly.
 */
function DisclosureCard({ symbol }: { symbol: string }) {
  const disclosures = useCompanyNews(symbol)
  const rows = disclosures.data?.items.slice(0, MAX_DISCLOSURES) ?? []

  return (
    <RailSection
      title="Công bố thông tin"
      note={
        <p className="mb-1.5 text-[12.5px] leading-relaxed text-ink-6">
          Công bố của <Figure>{symbol}</Figure> theo nghĩa vụ niêm yết, không phải bài báo.
        </p>
      }
    >
      {rows.length === 0 ? (
        <p className="py-2 text-meta text-ink-6">
          {disclosures.isPending
            ? "Đang tải công bố…"
            : disclosures.isError
              ? "Chưa đọc được công bố thông tin."
              : `Chưa có công bố nào của ${symbol}.`}
        </p>
      ) : (
        <ul className="grid grid-cols-fit">
          {rows.map((row) => (
            <li key={row.id} className="border-t border-hairline py-[13px] first:border-t-0">
              <span className="block text-pretty font-serif text-[16.5px] leading-[1.35] text-ink-3">
                {row.title}
              </span>
              <Figure className="mt-1.5 block text-[12px] text-ink-6">
                {formatStreamDate(row.published_at)}
              </Figure>
            </li>
          ))}
        </ul>
      )}
    </RailSection>
  )
}

/**
 * What the market is doing while the reader reads.
 *
 * The reference puts the weather here. This is a trading surface, so the index
 * is the weather — and the headline index is stated at figure size because it is
 * the one number that changes how every headline under it reads. The card is the
 * weather card's own shape: the place and its range on one line, the reading
 * large under it, and the days along the bottom.
 */
function MarketWidget() {
  const indices = useMarketIndices()
  const rows = indices.data ?? []
  const [headline, ...rest] = rows

  return (
    <div className="min-w-0 rounded-[14px] border border-border bg-surface-raised px-[18px] py-4">
      {headline ? (
        <>
          <div className="flex items-baseline justify-between gap-2 text-[13px]">
            <span className="min-w-0 truncate text-ink-5">{headline.name}</span>
            <Figure className={cn("shrink-0", deltaClass(headline.changePercent))}>
              {headline.changePercent >= 0 ? "▲" : "▼"}{" "}
              {Math.abs(headline.change).toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </Figure>
          </div>

          <div className="mt-2 flex items-baseline justify-between gap-2">
            <Figure
              className={cn(
                "font-serif text-[30px] leading-none tracking-[-0.02em]",
                deltaClass(headline.changePercent),
              )}
            >
              {headline.value.toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </Figure>
            <Figure className={cn("text-[13px]", deltaClass(headline.changePercent))}>
              {signedPercent(headline.changePercent)}
            </Figure>
          </div>

          {rest.length > 0 && (
            <div className="mt-4 flex gap-1.5 text-center">
              {rest.map((index) => (
                <div key={index.symbol} className="flex min-w-0 flex-1 flex-col gap-2">
                  <Figure className="truncate text-[12px] text-ink-6">{index.name}</Figure>
                  <Figure className={cn("text-[13.5px]", deltaClass(index.changePercent))}>
                    {signedPercent(index.changePercent)}
                  </Figure>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="text-meta text-ink-6">
          {indices.isPending ? "Đang tải chỉ số…" : "Chưa có dữ liệu chỉ số."}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Article

/**
 * One article, read in place — as much of it as the publisher actually gave us.
 *
 * A reading column of 740px and a serif face, because this is the one surface in
 * the product that is prose rather than figures. What fills that column is
 * whatever the source published: usually the summary, because CafeF's feed does
 * not carry the body and we deliberately do not scrape it — the text is
 * VCCorp's. So the summary is set as the reading text and the column ends in a
 * link to cafef.vn, which is where the rest of the article legitimately lives.
 * Paragraph breaks are taken from the text rather than inferred: a single block
 * would be a wall, and re-inferring paragraphs from sentence length would be
 * inventing structure the source did not publish.
 *
 * The first paragraph is set as the lede, above the picture, and the rest reads
 * under it — the design's own order. What the design has and this does not is
 * the section headings, the per-sentence citations and the "Điểm chính" box:
 * all three describe an article assembled from several outlets, and this feed
 * carries one publisher per item. Printing them would be printing structure the
 * source never sent.
 */
function ArticleScreen({
  article,
  items,
  categories,
  pending,
  isError,
  onRetry,
}: {
  article: FeedNewsItem | null
  items: FeedNewsItem[]
  categories: NewsCategory[]
  pending: boolean
  isError: boolean
  onRetry: () => void
}) {
  const { dispatch } = useShell()
  // Before the early return, because a hook cannot be conditional — and `null`
  // is exactly what tells the query not to fire for an article that is not open.
  const body = useNewsArticle(article?.url ?? null)
  const back = () => dispatch({ type: "news-article", article: null })

  if (article === null) {
    return (
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-1.5">
        <div className="mx-auto w-full max-w-[740px] py-10">
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
  const [lede, ...summaryRest] = bodyParagraphs(article)
  const facet = categoryLabel(categories, article.category)
  const blocks = body.data === undefined ? null : articleBody(body.data.blocks, article.summary)

  return (
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
      {/* Sticky inside the view rather than in the app's own header: the way
          back belongs to the article, and it must stay reachable from the
          bottom of a body several screens long. */}
      <div className="sticky top-0 z-20 border-b border-hairline bg-background/[0.86] backdrop-blur-[14px]">
        <div className="mx-auto flex max-w-[1180px] items-center gap-2.5 px-5 py-3 lg:px-9">
          <BackButton onClick={back} bordered />

          <div className="ml-auto flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => dispatch({ type: "open-inspector", tab: "news" })}
              className={cn(
                "flex shrink-0 items-center gap-2 whitespace-nowrap rounded-pill px-[17px] py-[9px] text-[14px] text-ink-5",
                "transition-colors hover:bg-surface-sunken hover:text-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <PanelRight className="size-[15px]" strokeWidth={1.7} />
              Nguồn
            </button>

            {article.url && (
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "flex shrink-0 items-center gap-2 whitespace-nowrap rounded-pill bg-primary px-[19px] py-[9px] text-[14px] font-medium text-primary-foreground",
                  "transition-[filter] hover:brightness-110",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <ExternalLink className="size-[15px]" strokeWidth={2} />
                Bài gốc
              </a>
            )}
          </div>
        </div>
      </div>

      <article className="mx-auto flex w-full max-w-[740px] flex-col gap-[26px] px-5 pb-24 pt-11">
        <h1 className="text-pretty font-serif text-[34px] font-normal leading-[1.1] tracking-[-0.022em] text-ink-display md:text-[46px]">
          {article.title}
        </h1>

        {lede && (
          <p className="text-pretty font-serif text-[19.5px] leading-[1.65] text-ink-2">{lede}</p>
        )}

        {article.url && <ShareRow url={article.url} title={article.title} />}

        <NewsImage item={article} scale="lg" className="aspect-[16/9] w-full rounded-xl" />

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 pb-1">
          <Figure className="text-[13px] text-ink-6">
            {formatPublishedDate(article.published_at)}
          </Figure>
          <div className="flex flex-wrap items-center gap-3">
            <SourceLine item={article} categories={categories} subject={false} />
            {/* A press article is about a story, not about a ticker, so the chip
                only appears on the items that genuinely name one — sending the
                reader to a symbol the article never mentioned would be worse
                than saying nothing. The facet stands in otherwise, as a label
                rather than a control, because there is nowhere for it to go. */}
            {article.symbol !== null ? (
              <SymbolChip symbol={article.symbol} />
            ) : (
              facet && (
                <span className="rounded-pill border border-border px-2.5 py-1 text-[12px] text-ink-5">
                  {facet}
                </span>
              )
            )}
          </div>
        </div>

        {summaryRest.map((paragraph, index) => (
          <p
            key={index}
            className="text-pretty font-serif text-[19px] leading-[1.68] text-ink-3"
          >
            {paragraph}
          </p>
        ))}

        {blocks !== null && <ArticleBody blocks={blocks} />}

        {/* The body is a second request behind the one that produced this
            screen, so the column is already readable — headline, lede, picture —
            while it lands. Saying which part is still coming beats a spinner
            over prose the reader can already read. */}
        {body.isPending && <QuietLine>Đang tải nội dung bài viết…</QuietLine>}

        {body.isError && article.url && (
          <div className="rounded-xl border border-border bg-surface-sunken px-4 py-3.5">
            <p className="text-[14px] text-ink-3">
              Chưa tải được nội dung đầy đủ của bài này.
            </p>
            <RetryButton onClick={() => void body.refetch()} className="mt-2.5" />
          </div>
        )}

        {lede === undefined && article.url === null && (
          // Genuinely nothing but a headline: no summary, no body, nowhere to
          // send the reader. The only case the old fallback was ever right for.
          <QuietLine>Nguồn tin chỉ cung cấp tiêu đề cho bài này.</QuietLine>
        )}

        {article.url && (
          <ReadOnSource
            url={article.url}
            source={article.source}
            extracted={blocks !== null && blocks.length > 0}
          />
        )}

        {related.length > 0 && (
          <section aria-label="Bài liên quan" className="mt-4">
            <h3 className="mb-[18px] font-serif text-[21px] font-medium text-ink-1">
              Bài liên quan
            </h3>
            <div className="grid grid-cols-2 gap-5 md:grid-cols-3">
              {related.map((item) => (
                <RelatedCard key={articleKey(item)} item={item} />
              ))}
            </div>
          </section>
        )}
      </article>
    </div>
  )
}

/**
 * The article's own body, drawn one block at a time.
 *
 * The API sends a tree rather than a string precisely so this can happen: a
 * subheading is set as a subheading and a photo keeps its caption, instead of
 * every block arriving as another paragraph. Blocks the extractor could not
 * type do not exist — it emits only these five — so there is no default arm to
 * write, and a kind added upstream renders nothing rather than something wrong.
 *
 * Keys are positional because a block has no id, and the list is replaced
 * wholesale by a refetch rather than reordered.
 */
function ArticleBody({ blocks }: { blocks: ArticleBlock[] }) {
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === "heading") {
          return (
            <h2
              key={index}
              className="mt-2 font-serif text-[25px] font-medium leading-[1.25] text-ink-1"
            >
              {block.text}
            </h2>
          )
        }

        if (block.kind === "quote") {
          return (
            <blockquote
              key={index}
              className="border-l-2 border-ink-6 pl-5 font-serif text-[19px] italic leading-[1.6] text-ink-2"
            >
              {block.text}
            </blockquote>
          )
        }

        if (block.kind === "list") {
          return (
            <ul key={index} className="flex list-disc flex-col gap-2 pl-6">
              {(block.items ?? []).map((entry, position) => (
                <li
                  key={position}
                  className="text-pretty font-serif text-[19px] leading-[1.68] text-ink-3"
                >
                  {entry}
                </li>
              ))}
            </ul>
          )
        }

        if (block.kind === "image") {
          return <BodyImage key={index} block={block} />
        }

        return (
          <p
            key={index}
            className="text-pretty font-serif text-[19px] leading-[1.68] text-ink-3"
          >
            {block.text}
          </p>
        )
      })}
    </>
  )
}

/**
 * One photo from inside the article, with the caption the publisher wrote.
 *
 * A body image that 404s is dropped rather than replaced by the lettered plate
 * the cards use: that plate exists so a *card* keeps its shape in a grid, and in
 * the middle of prose it would be a grey rectangle interrupting the reading for
 * no information at all. `alt` is the caption or empty — never the headline,
 * which would have a screen reader announce the title again mid-article.
 */
function BodyImage({ block }: { block: ArticleBlock }) {
  const [failed, setFailed] = useState(false)

  if (block.image_url === null || failed) return null

  return (
    <figure className="flex flex-col gap-2.5">
      <img
        src={block.image_url}
        alt={block.caption ?? ""}
        loading="lazy"
        onError={() => setFailed(true)}
        className="w-full rounded-xl bg-surface-sunken"
      />
      {block.caption && (
        <figcaption className="text-[13.5px] leading-relaxed text-ink-6">
          {block.caption}
        </figcaption>
      )}
    </figure>
  )
}

/**
 * The four ways out of a page the reader wants to pass on.
 *
 * Every one of them acts on the publisher's URL, which is why the row only
 * exists on items that carry one: sharing a link to our own feed position would
 * send the recipient somewhere they cannot open. Copy is the first because it is
 * the one that works into anything — Zalo, Messenger, a note — and the other
 * three are the networks' own intent endpoints, nothing embedded, no script from
 * a third party on the page.
 */
function ShareRow({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false)

  const targets = [
    {
      name: "Facebook",
      href: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
      icon: <Facebook className="size-[17px]" strokeWidth={1.7} />,
    },
    {
      name: "LinkedIn",
      href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
      icon: <Linkedin className="size-[17px]" strokeWidth={1.7} />,
    },
    {
      name: "X",
      href: `https://x.com/intent/post?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`,
      icon: <Twitter className="size-[17px]" strokeWidth={1.7} />,
    },
  ]

  const circle = cn(
    "flex size-10 items-center justify-center rounded-full border border-input text-ink-3 transition-colors",
    "hover:border-ink-6 hover:bg-surface-sunken hover:text-foreground",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
  )

  return (
    <div className="flex gap-[11px]" role="group" aria-label="Chia sẻ bài viết">
      <button
        type="button"
        title={copied ? "Đã sao chép liên kết" : "Sao chép liên kết"}
        aria-label={copied ? "Đã sao chép liên kết" : "Sao chép liên kết"}
        onClick={() => {
          void navigator.clipboard?.writeText(url).then(() => {
            setCopied(true)
            window.setTimeout(() => setCopied(false), 2000)
          })
        }}
        className={cn(circle, copied && "border-primary/50 text-primary")}
      >
        {copied ? (
          <Check className="size-[17px]" strokeWidth={2} />
        ) : (
          <Link2 className="size-[17px]" strokeWidth={1.7} />
        )}
      </button>

      {targets.map((target) => (
        <a
          key={target.name}
          href={target.href}
          target="_blank"
          rel="noopener noreferrer"
          title={`Chia sẻ lên ${target.name}`}
          aria-label={`Chia sẻ lên ${target.name}`}
          className={circle}
        >
          {target.icon}
        </a>
      ))}
    </div>
  )
}

/** What to read next, as the design draws it: a bordered card, picture on top. */
function RelatedCard({ item }: { item: FeedNewsItem }) {
  const { dispatch } = useShell()

  return (
    <button
      type="button"
      onClick={() => dispatch({ type: "news-article", article: articleKey(item) })}
      className={cn(
        "min-w-0 overflow-hidden rounded-xl border border-border bg-surface-raised text-left transition-colors",
        "hover:border-input hover:bg-surface-sunken",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <NewsImage item={item} className="aspect-[16/9] w-full border-b border-border" />
      <span className="flex flex-col gap-2.5 px-[15px] pb-4 pt-3.5">
        <span className="line-clamp-3 text-pretty text-[15px] font-medium leading-[1.35] text-ink-1">
          {item.title}
        </span>
        <Figure className="text-[12px] text-ink-6">{formatStreamDate(item.published_at)}</Figure>
      </span>
    </button>
  )
}

/** Re-asks for the feed. Both screens read the same query, so both offer it. */
function RetryButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <Button
      type="button"
      onClick={onClick}
      className={cn("px-3.5", className)}
    >
      Thử lại
    </Button>
  )
}

function BackButton({
  onClick,
  bordered = false,
  className,
}: {
  onClick: () => void
  /** Set in the article's own bar, where it is the row's first control. */
  bordered?: boolean
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-2 whitespace-nowrap rounded-pill text-[14px] text-ink-3 transition-colors",
        "hover:bg-surface-sunken hover:text-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        bordered ? "border border-input px-[17px] py-[9px] hover:border-ink-6" : "px-2.5 py-2",
        className,
      )}
    >
      <ArrowLeft className="size-[15px]" strokeWidth={1.8} />
      Trở về tin tức
    </button>
  )
}

/**
 * The way out of the reading column, stated once and unmissably.
 *
 * The header carries a "Bài gốc" affordance too, but a reader at the end of the
 * body is looking for what comes next, and a control they have to scroll back
 * up to find is a control that reads as absent.
 *
 * What it says depends on what the column managed to print. With the body
 * extracted, "read the whole thing there" would be false — the whole thing is
 * right here — so the link becomes attribution and names what the original
 * still has that an extract does not. Without it, the older promise stands: the
 * column ends after the summary on purpose, not because it broke.
 */
function ReadOnSource({
  url,
  source,
  extracted,
}: {
  url: string
  source: string
  /** Whether the column printed the article's body, not just its summary. */
  extracted: boolean
}) {
  return (
    <div className="mt-4 border-t border-border pt-7">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-pill bg-primary px-5 py-3 text-[14px] font-medium text-primary-foreground transition-[filter] hover:brightness-110"
      >
        <ExternalLink className="size-4" strokeWidth={1.8} />
        {extracted ? `Xem bài gốc trên ${source}` : `Đọc toàn bộ bài trên ${source}`}
      </a>
      <p className="mt-3 text-[13px] leading-relaxed text-ink-6">
        {extracted
          ? `Nội dung trên được trích từ bài gốc của ${source}. Bản gốc giữ đầy đủ hình ảnh, bảng biểu và định dạng.`
          : `Bảng tin chỉ hiển thị tiêu đề và phần tóm tắt; toàn văn bài viết ở lại trên ${source}.`}
      </p>
    </div>
  )
}

/** The reader's way from an article about a company into that company's board. */
function SymbolChip({ symbol }: { symbol: string }) {
  const { dispatch } = useShell()

  return (
    <button
      type="button"
      onClick={() =>
        dispatch({
          type: "select-symbol",
          selected: { symbol, name: symbol, exchange: "—" },
          open: true,
        })
      }
      className="rounded-pill border border-border px-2.5 py-1 text-[12px] text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
    >
      <Figure>{symbol}</Figure>
    </button>
  )
}

/**
 * The reading text: the body when there is one, the summary when there is not.
 *
 * For the press feed it is always the summary — `content` is null by design, not
 * by accident — so the summary is not a stand-in here so much as the whole of
 * what we are allowed to print.
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
 * Where an article came from: the source, what it is about, and when.
 *
 * The identity unit of this whole screen — every card, row and rail entry ends
 * with one, so a headline is never read without knowing who published it. What
 * it is *about* is the symbol on the items that name one and the facet on the
 * rest, which is most of the press feed: an empty gap there would read as a
 * field that failed to load rather than as a field that does not apply.
 *
 * The disc in front is the publisher's mark, drawn as a plate rather than
 * fetched: favicons come from the publisher's own host, and a row of hotlinked
 * icons would leak every reader's visit to every outlet in the feed.
 *
 * The date is opt-in because most of the surfaces that draw this already state
 * it somewhere the eye reaches first.
 */
export function SourceLine({
  item,
  categories = [],
  subject = true,
  withDate = false,
  className,
}: {
  item: {
    source: string
    symbol?: string | null
    category?: string | null
    published_at: string
  }
  categories?: NewsCategory[]
  /**
   * Whether to state what the item is about as well as who published it.
   *
   * Off in the reading column, which puts the subject in a chip of its own right
   * beside this — saying it twice in one row reads as one of the two having
   * fallen out of sync.
   */
  subject?: boolean
  withDate?: boolean
  className?: string
}) {
  const facet = categoryLabel(categories, item.category ?? null)

  return (
    <div className={cn("flex flex-wrap items-center gap-2 text-[12.5px] text-ink-6", className)}>
      <span className="flex items-center gap-2">
        <i
          aria-hidden="true"
          className="block size-[15px] shrink-0 rounded-full bg-surface-bubble"
        />
        <span>{item.source}</span>
      </span>
      {subject && (item.symbol ? <Figure>{item.symbol}</Figure> : facet && <span>{facet}</span>)}
      {withDate && item.published_at.trim() !== "" && (
        <Figure>· {formatStreamDate(item.published_at)}</Figure>
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
 * fail closed on the next source the provider adds — and CafeF serves from
 * cafefcdn.com, which is exactly such a host. The fallback covers both a missing
 * URL and a URL that turns out not to resolve: the reader gets a named plate
 * either way, and never a broken-image glyph in the middle of a card.
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
          "flex items-end overflow-hidden border border-border bg-surface-sunken p-2",
          className,
        )}
      >
        <Figure
          className={cn(
            "truncate font-serif lowercase text-ink-6",
            FALLBACK_FIGURE[scale],
          )}
        >
          {/* The symbol when the item has one, otherwise the publisher: a press
              article names no ticker, and an empty plate looks broken. */}
          {item.symbol ?? item.source}
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
    <div className="flex flex-col gap-[34px]" aria-busy="true">
      <span className="sr-only">Đang tải bảng tin</span>
      <div className="grid items-start gap-[30px] md:grid-cols-[300px_minmax(0,1fr)]">
        <div className="flex flex-col gap-[26px]">
          {[0, 1].map((slot) => (
            <div
              key={`spotlight-skeleton-${slot}`}
              className="h-[240px] animate-pulse rounded-[10px] border border-border bg-surface-raised"
            />
          ))}
        </div>
        <div className="h-[520px] animate-pulse rounded-xl border border-border bg-surface-raised" />
      </div>
      <Rule />
      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
        {[0, 1, 2, 3].map((slot) => (
          <div
            key={`grid-skeleton-${slot}`}
            className="h-[220px] animate-pulse rounded-[10px] border border-border bg-surface-raised"
          />
        ))}
      </div>
    </div>
  )
}
