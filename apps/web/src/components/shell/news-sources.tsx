"use client"

import { ExternalLink } from "lucide-react"

import { useNewsFeed } from "@/hooks/use-news"
import type { FeedNewsItem } from "@/lib/api"
import { articleKey, findArticle, formatPublishedDate } from "@/lib/news"

import { Eyebrow, Figure, PanelCard, QuietLine } from "./primitives"
import { useShell } from "./shell-state"
import { SourceLine } from "./view-news"

/** How many other articles about the same company the panel is willing to list. */
const MAX_OTHERS = 8

/**
 * Where the open article came from, and what else was written about the company.
 *
 * The panel exists because the reading column deliberately shows one article at
 * a time: the reader who wants to know whether two sources agree should not have
 * to leave the paragraph they are on to find out. It reads the same feed query
 * the view does — one request, two surfaces — so nothing here can describe a
 * moment the column behind it is not showing.
 */
export function NewsSourcesTab() {
  const { state, dispatch } = useShell()
  const feed = useNewsFeed()

  const items = feed.data?.items ?? []
  const article = findArticle(items, state.newsArticle)

  if (state.newsArticle === null) {
    return <QuietLine>Mở một bài viết để xem nguồn.</QuietLine>
  }

  if (article === null) {
    return (
      <QuietLine>
        {feed.isPending ? "Đang tải nguồn tin…" : "Bài viết không còn trong bảng tin."}
      </QuietLine>
    )
  }

  const others = items
    .filter((item) => item.symbol === article.symbol && articleKey(item) !== articleKey(article))
    .slice(0, MAX_OTHERS)

  return (
    <div>
      <Eyebrow>Nguồn tham khảo</Eyebrow>
      <div className="mt-2.5">
        <SourceEntry item={article} current />
      </div>

      <div className="mt-5 flex items-baseline gap-2">
        <span className="text-[0.95rem] text-ink-1">
          Tin khác về <Figure>{article.symbol}</Figure>
        </span>
      </div>
      {others.length === 0 ? (
        <QuietLine>Chưa có bài nào khác về mã này trong bảng tin.</QuietLine>
      ) : (
        <div className="mt-2.5 grid grid-cols-fit gap-2">
          {others.map((item) => (
            <SourceEntry
              key={articleKey(item)}
              item={item}
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
 * The open one is not a control — pressing it would go where the reader already
 * is — so it is drawn as a card instead, and its own row keeps the primary tint
 * to say which of the entries the column is showing.
 */
function SourceEntry({
  item,
  current = false,
  onOpen,
}: {
  item: FeedNewsItem
  current?: boolean
  onOpen?: () => void
}) {
  const body = (
    <>
      <div className="flex items-start gap-2">
        <SourceLine item={item} />
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
    return <PanelCard className="min-w-0 border-primary/25">{body}</PanelCard>
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
