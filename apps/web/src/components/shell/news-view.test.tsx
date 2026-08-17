// @vitest-environment jsdom
/**
 * What the news view promises when the feed does not arrive.
 *
 * The regression this file exists for: the query provider sends every refused
 * request to the ErrorBoundary, so a feed that answered 404 replaced the entire
 * shell — the conversation and the board with it — because one pane of headlines
 * failed. The view has to absorb its own failure instead, and it has to tell the
 * two failures apart: a feed that did not load is not an article that has
 * scrolled out of one.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { NewsFeedResponse } from "@/lib/api"

const feed = {
  data: undefined as NewsFeedResponse | undefined,
  isPending: false,
  isError: false,
  isFetching: false,
  dataUpdatedAt: 0,
  refetch: vi.fn(),
}

vi.mock("@/hooks/use-news", () => ({ useNewsFeed: () => feed }))

vi.mock("@/hooks/use-market-indices", () => ({
  useMarketIndices: () => ({ data: [], isPending: false }),
}))

import { NewsView } from "./view-news"
import { ShellProvider, useShell } from "./shell-state"

afterEach(cleanup)

beforeEach(() => {
  feed.data = undefined
  feed.isPending = false
  feed.isError = false
  feed.refetch = vi.fn()
})

/** Puts the view in front of one article without going through the feed. */
function OpenArticle({ article }: { article: string }) {
  const { state, dispatch } = useShell()
  if (state.newsArticle !== article) {
    dispatch({ type: "news-article", article })
  }
  return <NewsView />
}

function renderNews(children: React.ReactNode) {
  return render(<ShellProvider>{children}</ShellProvider>)
}

describe("the feed screen", () => {
  it("reports a refused feed in place, and keeps the retry reachable", () => {
    feed.isError = true

    renderNews(<NewsView />)

    expect(screen.getByText("Chưa đọc được tin tức.")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }))
    expect(feed.refetch).toHaveBeenCalledTimes(1)
  })

  it("says the feed is empty rather than broken when it answered with nothing", () => {
    feed.data = { items: [], symbols: [], generated_at: "", total_count: 0 }

    renderNews(<NewsView />)

    expect(screen.getByText("Chưa có tin tức nào trong bảng tin.")).toBeInTheDocument()
    expect(screen.queryByText("Chưa đọc được tin tức.")).not.toBeInTheDocument()
  })
})

describe("the reading column, with no article to read", () => {
  it("blames the request, not the feed's contents, when the feed failed", () => {
    feed.isError = true

    renderNews(<OpenArticle article="VCB:1" />)

    expect(screen.getByText("Chưa đọc được bài viết.")).toBeInTheDocument()
    expect(screen.queryByText("Bài viết không còn trong bảng tin.")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }))
    expect(feed.refetch).toHaveBeenCalledTimes(1)
  })

  it("says the article has left the feed when the feed itself loaded", () => {
    feed.data = { items: [], symbols: [], generated_at: "", total_count: 0 }

    renderNews(<OpenArticle article="VCB:1" />)

    expect(screen.getByText("Bài viết không còn trong bảng tin.")).toBeInTheDocument()
  })

  it("offers the way back out of both dead ends", () => {
    feed.isError = true

    renderNews(<OpenArticle article="VCB:1" />)

    expect(screen.getByRole("button", { name: /Trở về tin tức/ })).toBeInTheDocument()
  })
})
