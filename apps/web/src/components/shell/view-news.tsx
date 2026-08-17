"use client"

import { useMemo, useState, type ReactNode } from "react"
import { ArrowLeft, ExternalLink, PanelRight } from "lucide-react"

import { useMarketIndices } from "@/hooks/use-market-indices"
import { useCompanyNews, useNewsCategories, useNewsFeed } from "@/hooks/use-news"
import type { FeedNewsItem, NewsCategory } from "@/lib/api"
import {
  articleKey,
  findArticle,
  formatPublishedDate,
  formatStreamDate,
  partitionFeed,
  relatedArticles,
} from "@/lib/news"
import { cn } from "@/lib/utils"

import { Card, deltaClass, Eyebrow, Figure, PanelCard, QuietLine, signedPercent } from "./primitives"
import { useShell } from "./shell-state"

/** The facet the screen opens on, and the one the API answers with by default. */
export const DEFAULT_CATEGORY = "moi-nhat"

/** How many of a company's disclosures the rail is willing to list. */
const MAX_DISCLOSURES = 5

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
 * What the screen will *not* do is pretend to hold more of an article than the
 * publisher gave us. CafeF's feed carries a headline, a summary and a picture;
 * the full text stays on cafef.vn, and every reading surface here ends by
 * pointing at it rather than by trailing off.
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
    <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-1.5">
      <div className="mx-auto grid max-w-[1180px] gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          {categories.length > 0 && (
            <PillRow categories={categories} category={category} onCategory={onCategory} />
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
                <section aria-label="Tin đáng chú ý" className="mt-6 grid grid-cols-2 gap-5 lg:grid-cols-4">
                  {blocks.grid.map((item) => (
                    <SmallCard key={articleKey(item)} item={item} categories={categories} />
                  ))}
                </section>
              )}

              {blocks.stream.length > 0 && <Stream items={blocks.stream} categories={categories} />}
            </>
          )}
        </div>

        <Rail items={items} categories={categories} />
      </div>
    </div>
  )
}

/**
 * The facets the API offers, as the reader's way of narrowing the feed.
 *
 * Every pill is a different request, not a filter over one list: the press feed
 * is per-category upstream, so there is no single response holding all of them
 * to sift on the client.
 */
function PillRow({
  categories,
  category,
  onCategory,
}: {
  categories: NewsCategory[]
  category: string
  onCategory: (slug: string) => void
}) {
  return (
    // The row scrolls rather than wraps: a second line of pills reads as a
    // second control, and the first pill must stay where the eye left it.
    <div
      role="group"
      aria-label="Lọc bảng tin theo chủ đề"
      className="scrollbar-thin -mx-1 flex gap-1 overflow-x-auto px-1 pb-0.5"
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
    <section aria-label="Tin nổi bật" className="mt-3.5 grid gap-5 md:grid-cols-[264px_minmax(0,1fr)]">
      <div className="order-2 grid content-start gap-5 md:order-1">
        {spotlight.map((item) => (
          <SmallCard key={articleKey(item)} item={item} categories={categories} />
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
        <SourceLine item={hero} categories={categories} withDate className="mt-2.5" />
      </ArticleLink>
    </section>
  )
}

/** The anatomy every card on this screen repeats: image, headline, identity. */
function SmallCard({ item, categories }: { item: FeedNewsItem; categories: NewsCategory[] }) {
  return (
    <ArticleLink item={item} className="min-w-0">
      <NewsImage item={item} className="aspect-[16/9] w-full rounded-xl" />
      <h3 className="mt-2 line-clamp-3 text-row leading-snug text-ink-1">{item.title}</h3>
      <SourceLine item={item} categories={categories} className="mt-1.5" />
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
function Stream({ items, categories }: { items: FeedNewsItem[]; categories: NewsCategory[] }) {
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
              <SourceLine item={item} categories={categories} className="mt-2" />
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
 * The right-hand rail: the session, the newest headlines, and the filings.
 *
 * Hidden below `xl` rather than stacked under the feed. Everything in it is
 * context for the column beside it, and context that sits below the whole feed
 * is context nobody reaches.
 */
function Rail({ items, categories }: { items: FeedNewsItem[]; categories: NewsCategory[] }) {
  const { state, dispatch } = useShell()
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
                  <Figure className="mt-1 block text-micro text-ink-6">
                    {item.symbol ?? categoryLabel(categories, item.category)}
                  </Figure>
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

      <DisclosureCard symbol={state.selected.symbol} />
    </aside>
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
 */
function DisclosureCard({ symbol }: { symbol: string }) {
  const disclosures = useCompanyNews(symbol)
  const rows = disclosures.data?.items.slice(0, MAX_DISCLOSURES) ?? []

  return (
    <Card className="min-w-0">
      <Eyebrow>Công bố thông tin</Eyebrow>
      <p className="mt-1.5 text-micro leading-relaxed text-ink-6">
        Công bố của <Figure>{symbol}</Figure> theo nghĩa vụ niêm yết, không phải bài báo.
      </p>

      {rows.length === 0 ? (
        <p className="mt-2 text-meta text-ink-6">
          {disclosures.isPending
            ? "Đang tải công bố…"
            : disclosures.isError
              ? "Chưa đọc được công bố thông tin."
              : `Chưa có công bố nào của ${symbol}.`}
        </p>
      ) : (
        <ul className="mt-2 grid grid-cols-fit">
          {rows.map((row) => (
            <li key={row.id} className="border-t border-hairline py-2 first:border-t-0">
              <span className="block text-control leading-snug text-ink-2">{row.title}</span>
              <Figure className="mt-1 block text-micro text-ink-6">
                {formatStreamDate(row.published_at)}
              </Figure>
            </li>
          ))}
        </ul>
      )}
    </Card>
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
 * One article, read in place — as much of it as the publisher actually gave us.
 *
 * A reading column of 720px and a serif face, because this is the one surface in
 * the product that is prose rather than figures. What fills that column is
 * whatever the source published: usually the summary, because CafeF's feed does
 * not carry the body and we deliberately do not scrape it — the text is
 * VCCorp's. So the summary is set as the reading text and the column ends in a
 * link to cafef.vn, which is where the rest of the article legitimately lives.
 * Paragraph breaks are taken from the text rather than inferred: a single block
 * would be a wall, and re-inferring paragraphs from sentence length would be
 * inventing structure the source did not publish.
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
          <SourceLine item={article} categories={categories} subject={false} />
          {/* A press article is about a story, not about a ticker, so the chip
              only appears on the items that genuinely name one — sending the
              reader to a symbol the article never mentioned would be worse than
              saying nothing. The facet stands in otherwise, as a label rather
              than a control, because there is nowhere for it to go. */}
          {article.symbol !== null ? (
            <SymbolChip symbol={article.symbol} />
          ) : (
            article.category !== null && (
              <span className="rounded-pill border border-border px-2.5 py-1 text-micro text-ink-4">
                {categoryLabel(categories, article.category)}
              </span>
            )
          )}
        </div>

        <NewsImage item={article} scale="lg" className="mt-6 aspect-[16/9] w-full rounded-card" />

        {paragraphs.length > 0 ? (
          <div className="mt-6 grid gap-4 font-serif text-[1.05rem] leading-[1.75] text-ink-2">
            {paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        ) : article.url === null ? (
          // Genuinely nothing but a headline: no summary, no body, nowhere to
          // send the reader. The only case the old fallback was ever right for.
          <div className="mt-6">
            <QuietLine>Nguồn tin chỉ cung cấp tiêu đề cho bài này.</QuietLine>
          </div>
        ) : null}

        {article.url && <ReadOnSource url={article.url} source={article.source} />}

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
 * The way out of the reading column, stated once and unmissably.
 *
 * The header carries a "Bài gốc" affordance too, but a reader who has just
 * finished the summary is at the bottom of the column and looking for what
 * comes next — a control they have to scroll back up to find is a control that
 * reads as absent. The line under it exists so the ending does not feel like a
 * truncation bug: the full text is not missing, it is on the publisher's site
 * on purpose.
 */
function ReadOnSource({ url, source }: { url: string; source: string }) {
  return (
    <div className="mt-7 border-t border-border pt-6">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-[10px] bg-primary px-4 py-2.5 text-control font-medium text-primary-foreground transition-[filter] hover:brightness-110"
      >
        <ExternalLink className="size-4" strokeWidth={1.7} />
        Đọc toàn bộ bài trên {source}
      </a>
      <p className="mt-2.5 text-meta leading-relaxed text-ink-6">
        Bảng tin chỉ hiển thị tiêu đề và phần tóm tắt; toàn văn bài viết ở lại trên {source}.
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
      className="rounded-pill border border-border px-2.5 py-1 text-micro text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground"
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
    <div className={cn("flex flex-wrap items-center gap-1.5 text-micro text-ink-5", className)}>
      <span className="rounded-pill bg-foreground/[0.06] px-1.5 py-0.5 lowercase">
        {item.source}
      </span>
      {subject && (item.symbol ? <Figure>{item.symbol}</Figure> : facet && <span>{facet}</span>)}
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
          "flex items-center justify-center overflow-hidden bg-surface-sunken",
          className,
        )}
      >
        <Figure className={cn("font-serif text-ink-6", FALLBACK_FIGURE[scale])}>
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
