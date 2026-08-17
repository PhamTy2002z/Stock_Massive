"use client"

import { ExternalLink } from "lucide-react"

import { useNewsFeed } from "@/hooks/use-news"
import type { FeedNewsItem, NewsCategory } from "@/lib/api"
import { articleFacet, articleKey, findArticle, formatPublishedDate } from "@/lib/news"

import { Eyebrow, PanelCard, QuietLine } from "./primitives"
import { useShell } from "./shell-state"
import { DEFAULT_CATEGORY, SourceLine } from "./view-news"

/** How many other articles on the same subject the panel is willing to list. */
const MAX_OTHERS = 8

/**
 * Where the open article came from, and what else was written on the subject.
 *
 * The panel exists because the reading column deliberately shows one article at
 * a time: the reader who wants to know whether two sources agree should not have
 * to leave the paragraph they are on to find out. It reads the same feed query
 * the view does — one request, two surfaces — so nothing here can describe a
 * moment the column behind it is not showing. Which facet that is comes out of
 * the article's key rather than out of the shell: the key is namespaced by the
 * article's own category, so it already says which feed holds it.
 */
export function NewsSourcesTab() {
  const { state, dispatch } = useShell()
  const feed = useNewsFeed(
    state.newsArticle === null ? DEFAULT_CATEGORY : articleFacet(state.newsArticle),
  )

  const items = feed.data?.items ?? []
  const categories: NewsCategory[] = feed.data?.categories ?? []
  const article = findArticle(items, state.newsArticle)

  if (state.newsArticle === null) {
    return <QuietLine>Mở một bài viết để xem nguồn.</QuietLine>
  }

  if (article === null) {
    // Same distinction the reading column makes: a feed that failed to load is
    // not an article that has left it.
    return (
      <QuietLine>
        {feed.isError
          ? "Chưa đọc được nguồn tin."
          : feed.isPending
            ? "Đang tải nguồn tin…"
            : "Bài viết không còn trong bảng tin."}
      </QuietLine>
    )
  }

  const others = items
    .filter(
      (item) => item.category === article.category && articleKey(item) !== articleKey(article),
    )
    .slice(0, MAX_OTHERS)

  return (
    <div>
      <Eyebrow>Nguồn tham khảo</Eyebrow>
      <div className="mt-2.5">
        <SourceEntry item={article} categories={categories} current />
      </div>

      <div className="mt-5 flex items-baseline gap-2">
        <span className="text-[0.95rem] text-ink-1">Tin khác cùng chủ đề</span>
      </div>
      {others.length === 0 ? (
        <QuietLine>Chưa có bài nào khác về chủ đề này trong bảng tin.</QuietLine>
      ) : (
        <div className="mt-2.5 grid grid-cols-fit gap-2">
          {others.map((item) => (
            <SourceEntry
              key={articleKey(item)}
              item={item}
              categories={categories}
              onOpen={() => dispatch({ type: "news-article", article: articleKey(item) })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * One source, in the same anatomy whether it is the open article or another.
 *
 * The open one keeps the primary tint that says which of the entries the column
 * is showing, but it is a control now rather than a card: the point of naming
 * the source is that the reader can go and read it, and this feed only ever
 * holds the opening of an article. Pressing another entry still swaps the
 * column, because that one *is* somewhere else to go inside the app.
 */
function SourceEntry({
  item,
  categories,
  current = false,
  onOpen,
}: {
  item: FeedNewsItem
  categories: NewsCategory[]
  current?: boolean
  onOpen?: () => void
}) {
  const body = (
    <>
      <div className="flex items-start gap-2">
        <SourceLine item={item} categories={categories} />
        {item.url && (
          <ExternalLink
            className="ml-auto mt-0.5 size-3.5 shrink-0 text-ink-6"
            strokeWidth={1.7}
            aria-hidden="true"
          />
        )}
      </div>

      <div className="mt-1.5 text-control leading-snug text-ink-1">{item.title}</div>
      {item.summary && (
        <p className="mt-1 line-clamp-2 text-meta leading-relaxed text-ink-5">{item.summary}</p>
      )}
      <div className="mt-1.5 text-micro text-ink-6">{formatPublishedDate(item.published_at)}</div>
    </>
  )

  if (current) {
    if (item.url === null) {
      return <PanelCard className="min-w-0 border-primary/25">{body}</PanelCard>
    }

    return (
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block min-w-0 rounded-xl border border-primary/25 bg-surface-sunken p-3 transition-colors hover:bg-foreground/[0.05]"
      >
        {body}
      </a>
    )
  }

  return (
    <button
      type="button"
      onClick={onOpen}
      className="min-w-0 rounded-xl border border-border bg-surface-sunken p-3 text-left transition-colors hover:bg-foreground/[0.05]"
    >
      {body}
    </button>
  )
}
