// @vitest-environment jsdom
/**
 * What the news view promises about the feed it is actually given.
 *
 * Two regressions live here. The first: the query provider sends every refused
 * request to the ErrorBoundary, so a feed that answered 404 replaced the entire
 * shell — the conversation and the board with it — because one pane of headlines
 * failed. The view has to absorb its own failure, and it has to tell the two
 * failures apart, because a feed that did not load is not an article that has
 * scrolled out of one.
 *
 * The second: the reader used to end on "Nguồn tin chỉ cung cấp tiêu đề cho bài
 * này." for every article, because it looked for a `content` the press feed does
 * not carry and never noticed the summary and the link that it does. So the
 * tests below pin what the reading column owes a CafeF article — the summary as
 * the body, and a way through to the original — and pin that bare-headline line
 * to the one case it is true of.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type {
  ArticleBlock,
  CompanyNewsResponse,
  FeedNewsItem,
  NewsArticleResponse,
  NewsFeedResponse,
} from "@/lib/api"

/** The registry the API serves, trimmed to the facets these tests press. */
const CATEGORIES = [
  { slug: "moi-nhat", label: "Mới nhất" },
  { slug: "chung-khoan", label: "Chứng khoán" },
  { slug: "vi-mo", label: "Vĩ mô" },
]

const feed = {
  data: undefined as NewsFeedResponse | undefined,
  isPending: false,
  isError: false,
  isFetching: false,
  dataUpdatedAt: 0,
  refetch: vi.fn(),
}

/** Records which facet the view asked for, which is the point of the pill row. */
const feedSpy = vi.fn((_category: string) => feed)

const categories = {
  data: CATEGORIES as NewsFeedResponse["categories"] | undefined,
  isPending: false,
  isError: false,
}

const companyNews = {
  data: undefined as CompanyNewsResponse | undefined,
  isPending: false,
  isError: false,
}

/** The article body lane, which only fires once a reader opens something. */
const articleBodyQuery = {
  data: undefined as NewsArticleResponse | undefined,
  isPending: false,
  isError: false,
  refetch: vi.fn(),
}

/** Records the URL the reading column asked for, or `null` when it asked for none. */
const articleSpy = vi.fn((_url: string | null) => articleBodyQuery)

vi.mock("@/hooks/use-news", () => ({
  useNewsFeed: (category: string) => feedSpy(category),
  useNewsCategories: () => categories,
  useCompanyNews: () => companyNews,
  useNewsArticle: (url: string | null) => articleSpy(url),
}))

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
  feedSpy.mockClear()
  categories.data = CATEGORIES
  companyNews.data = undefined
  articleBodyQuery.data = undefined
  articleBodyQuery.isPending = false
  articleBodyQuery.isError = false
  articleBodyQuery.refetch = vi.fn()
  articleSpy.mockClear()
})

/** One block of an article body, defaulted to the prose case. */
function block(overrides: Partial<ArticleBlock> = {}): ArticleBlock {
  return {
    kind: "paragraph",
    text: null,
    items: null,
    image_url: null,
    caption: null,
    ...overrides,
  }
}

/** An article body response around some blocks. */
function articleResponse(
  blocks: ArticleBlock[],
  url = "https://cafef.vn/a-1.chn",
): NewsArticleResponse {
  return {
    url,
    source: "CafeF",
    blocks,
    content: blocks.map((entry) => entry.text ?? "").join("\n"),
  }
}

/** One press item: a string id, a facet, and no symbol — the CafeF shape. */
function item(overrides: Partial<FeedNewsItem> & { id: string }): FeedNewsItem {
  return {
    title: `Tin ${overrides.id}`,
    source: "CafeF",
    published_at: "2026-08-17T19:59:00+07:00",
    summary: null,
    content: null,
    url: null,
    image_url: null,
    category: "chung-khoan",
    symbol: null,
    price: null,
    price_change_pct: null,
    ...overrides,
  }
}

/** A feed response around some items, with the registry the API sends with it. */
function response(items: FeedNewsItem[], category = "moi-nhat"): NewsFeedResponse {
  return {
    items,
    category,
    categories: CATEGORIES,
    symbols: [],
    generated_at: "2026-08-17T20:10:00+07:00",
    total_count: items.length,
  }
}

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
    feed.data = response([])

    renderNews(<NewsView />)

    expect(screen.getByText("Chưa có tin tức nào trong bảng tin.")).toBeInTheDocument()
    expect(screen.queryByText("Chưa đọc được tin tức.")).not.toBeInTheDocument()
  })

  it("keeps the pill row standing when the feed itself refused", () => {
    feed.isError = true

    renderNews(<NewsView />)

    // The registry is its own query for exactly this: the reader whose facet
    // failed still needs a way to ask for a different one.
    expect(screen.getByRole("button", { name: "Chứng khoán" })).toBeInTheDocument()
  })

  it("falls back to the facets the feed named when the registry did not load", () => {
    categories.data = undefined
    feed.data = response([])

    renderNews(<NewsView />)

    expect(screen.getByRole("button", { name: "Vĩ mô" })).toBeInTheDocument()
  })
})

describe("the pill row", () => {
  it("opens on the newest facet", () => {
    feed.data = response([])

    renderNews(<NewsView />)

    expect(feedSpy).toHaveBeenCalledWith("moi-nhat")
    expect(screen.getByRole("button", { name: "Mới nhất" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("asks the API for the facet that was pressed", () => {
    feed.data = response([])

    renderNews(<NewsView />)
    fireEvent.click(screen.getByRole("button", { name: "Chứng khoán" }))

    // A different request, not a filter over the one already held: the press
    // feed is per-category upstream.
    expect(feedSpy).toHaveBeenLastCalledWith("chung-khoan")
    expect(screen.getByRole("button", { name: "Chứng khoán" })).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("names the facet in the empty state once the reader has left the default", () => {
    feed.data = response([])

    renderNews(<NewsView />)
    fireEvent.click(screen.getByRole("button", { name: "Vĩ mô" }))

    expect(screen.getByText("Chưa có tin nào trong chủ đề Vĩ mô.")).toBeInTheDocument()
  })
})

describe("the stream", () => {
  /** A feed long enough to overflow the blocks above the stream and then some. */
  function longFeed(count: number) {
    return response(Array.from({ length: count }, (_, index) => item({ id: String(index) })))
  }

  it("opens on one page of rows and reveals the rest on request", () => {
    // Seven items are taken by the lead, the spotlight and the grid, so a feed
    // of twenty leaves thirteen dated rows — one page and a bit.
    feed.data = longFeed(20)

    renderNews(<NewsView />)

    // Rows seven through fourteen are the first page; the last five wait.
    expect(screen.getByText("Tin 14")).toBeInTheDocument()
    expect(screen.queryByText("Tin 15")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Xem thêm tin" }))

    expect(screen.getByText("Tin 19")).toBeInTheDocument()
    // Nothing left behind it, so the button goes rather than pressing to nothing.
    expect(screen.queryByRole("button", { name: "Xem thêm tin" })).not.toBeInTheDocument()
  })

  it("offers nothing to expand when the stream already fits", () => {
    feed.data = longFeed(12)

    renderNews(<NewsView />)

    expect(screen.getByText("Tin 11")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Xem thêm tin" })).not.toBeInTheDocument()
  })
})

describe("the reading column", () => {
  it("sets the summary as the body and sends the reader to the original", () => {
    feed.data = response([
      item({
        id: "188260817190901375",
        title: "Hoàn thiện thước đo rủi ro thị trường trái phiếu",
        summary: "Xếp hạng tín nhiệm đã có khung pháp lý.",
        url: "https://cafef.vn/hoan-thien-188260817190901375.chn",
      }),
    ])

    renderNews(<OpenArticle article="chung-khoan:188260817190901375" />)

    expect(screen.getByText("Xếp hạng tín nhiệm đã có khung pháp lý.")).toBeInTheDocument()

    const cta = screen.getByRole("link", { name: /Đọc toàn bộ bài trên CafeF/ })
    expect(cta).toHaveAttribute("href", "https://cafef.vn/hoan-thien-188260817190901375.chn")
    expect(cta).toHaveAttribute("target", "_blank")
    expect(cta).toHaveAttribute("rel", "noopener noreferrer")

    // And it says why the column ends there, rather than looking truncated.
    expect(
      screen.getByText(/toàn văn bài viết ở lại trên CafeF/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByText("Nguồn tin chỉ cung cấp tiêu đề cho bài này."),
    ).not.toBeInTheDocument()
  })

  it("prints the article's body and asks for it by the publisher's URL", () => {
    feed.data = response([
      item({
        id: "1",
        summary: "Xếp hạng tín nhiệm đã có khung pháp lý.",
        url: "https://cafef.vn/a-1.chn",
      }),
    ])
    articleBodyQuery.data = articleResponse([
      block({ text: "Đoạn mở đầu của bài viết, đủ dài để đọc như một đoạn văn." }),
      block({ kind: "heading", text: "Khi nào dòng vốn quay lại?" }),
      block({ kind: "list", items: ["Điều thứ nhất", "Điều thứ hai"] }),
    ])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(articleSpy).toHaveBeenCalledWith("https://cafef.vn/a-1.chn")
    expect(
      screen.getByText("Đoạn mở đầu của bài viết, đủ dài để đọc như một đoạn văn."),
    ).toBeInTheDocument()
    // A subheading is set as one, which is the whole point of sending blocks
    // rather than a string.
    expect(
      screen.getByRole("heading", { name: "Khi nào dòng vốn quay lại?", level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
    expect(screen.getByText("Điều thứ hai")).toBeInTheDocument()
  })

  it("does not ask for a body until an article is open", () => {
    feed.data = response([item({ id: "1", url: "https://cafef.vn/a-1.chn" })])

    renderNews(<NewsView />)

    // The reading column is not mounted on the feed, so the publisher is not
    // asked for the body of a headline nobody pressed.
    expect(articleSpy).not.toHaveBeenCalled()
  })

  it("stops promising the rest of the article once it has printed it", () => {
    feed.data = response([item({ id: "1", url: "https://cafef.vn/a-1.chn" })])
    articleBodyQuery.data = articleResponse([
      block({ text: "Toàn văn bài viết đã nằm ngay trong cột đọc này." }),
    ])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    // "Read the whole thing there" would be false when the whole thing is here.
    expect(screen.getByRole("link", { name: /Xem bài gốc trên CafeF/ })).toBeInTheDocument()
    expect(screen.queryByText(/toàn văn bài viết ở lại trên CafeF/i)).not.toBeInTheDocument()
    expect(screen.getByText(/được trích từ bài gốc của CafeF/i)).toBeInTheDocument()
  })

  it("draws a body photo with its caption, and never the headline as alt text", () => {
    feed.data = response([
      item({ id: "1", title: "Tiêu đề bài", url: "https://cafef.vn/a-1.chn" }),
    ])
    articleBodyQuery.data = articleResponse([
      block({
        kind: "image",
        image_url: "https://cafefcdn.com/anh.png",
        caption: "Mai Văn Chỉ cùng tang vật.",
      }),
    ])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    const photo = screen.getByAltText("Mai Văn Chỉ cùng tang vật.")
    expect(photo).toHaveAttribute("src", "https://cafefcdn.com/anh.png")
    expect(screen.getByText("Mai Văn Chỉ cùng tang vật.")).toBeInTheDocument()
    expect(screen.queryByAltText("Tiêu đề bài")).not.toBeInTheDocument()
  })

  it("does not print the standfirst twice when the body repeats it", () => {
    const sapo =
      "Theo ông Minh, điều quan trọng trong giai đoạn hiện tại không phải là dự đoán thị trường."
    feed.data = response([item({ id: "1", summary: sapo, url: "https://cafef.vn/a-1.chn" })])
    articleBodyQuery.data = articleResponse([
      block({ text: "Năm 2026 là một năm không dễ dàng với thị trường chứng khoán." }),
      block({ text: sapo }),
    ])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getAllByText(sapo)).toHaveLength(1)
  })

  it("stays readable while the body is still in flight", () => {
    feed.data = response([
      item({
        id: "1",
        title: "Tiêu đề đã có",
        summary: "Tóm tắt đã có.",
        url: "https://cafef.vn/a-1.chn",
      }),
    ])
    articleBodyQuery.isPending = true

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByText("Tiêu đề đã có")).toBeInTheDocument()
    expect(screen.getByText("Tóm tắt đã có.")).toBeInTheDocument()
    expect(screen.getByText("Đang tải nội dung bài viết…")).toBeInTheDocument()
  })

  it("offers a retry for the body alone when only the body refused", () => {
    feed.data = response([
      item({ id: "1", summary: "Tóm tắt đã có.", url: "https://cafef.vn/a-1.chn" }),
    ])
    articleBodyQuery.isError = true

    renderNews(<OpenArticle article="chung-khoan:1" />)

    // The feed loaded, so the article is still readable down to its summary —
    // this must not be reported as the feed failing.
    expect(screen.getByText("Tóm tắt đã có.")).toBeInTheDocument()
    expect(screen.queryByText("Chưa đọc được bài viết.")).not.toBeInTheDocument()
    expect(screen.getByText("Chưa tải được nội dung đầy đủ của bài này.")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }))
    expect(articleBodyQuery.refetch).toHaveBeenCalled()
    expect(feed.refetch).not.toHaveBeenCalled()
  })

  it("still offers the original when the summary is missing but the link is not", () => {
    feed.data = response([item({ id: "1", url: "https://cafef.vn/a-1.chn" })])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByRole("link", { name: /Đọc toàn bộ bài trên CafeF/ })).toBeInTheDocument()
    expect(
      screen.queryByText("Nguồn tin chỉ cung cấp tiêu đề cho bài này."),
    ).not.toBeInTheDocument()
  })

  it("admits to a bare headline only when there is genuinely nothing else", () => {
    feed.data = response([item({ id: "1" })])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByText("Nguồn tin chỉ cung cấp tiêu đề cho bài này.")).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /Đọc toàn bộ bài/ })).not.toBeInTheDocument()
  })

  it("shares the publisher's own link, and only when there is one to share", () => {
    feed.data = response([
      item({ id: "1", title: "Fed giữ nguyên lãi suất", url: "https://cafef.vn/a-1.chn" }),
    ])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    // The networks' own intent endpoints, carrying the article's URL — nothing
    // embedded, and nothing pointing at our own feed position.
    expect(screen.getByRole("link", { name: "Chia sẻ lên Facebook" })).toHaveAttribute(
      "href",
      "https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fcafef.vn%2Fa-1.chn",
    )
    expect(screen.getByRole("link", { name: "Chia sẻ lên X" })).toHaveAttribute(
      "href",
      "https://x.com/intent/post?url=https%3A%2F%2Fcafef.vn%2Fa-1.chn&text=Fed%20gi%E1%BB%AF%20nguy%C3%AAn%20l%C3%A3i%20su%E1%BA%A5t",
    )
    expect(screen.getByRole("button", { name: "Sao chép liên kết" })).toBeInTheDocument()
  })

  it("withholds the share row from an article that has no link behind it", () => {
    feed.data = response([item({ id: "1" })])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.queryByRole("group", { name: "Chia sẻ bài viết" })).not.toBeInTheDocument()
  })

  it("labels a press article with its facet, since it names no symbol", () => {
    feed.data = response([item({ id: "1", category: "vi-mo" })])

    renderNews(<OpenArticle article="vi-mo:1" />)

    expect(screen.getAllByText("Vĩ mô").length).toBeGreaterThan(0)
  })

  it("offers the symbol as a way into the board when the item names one", () => {
    feed.data = response([item({ id: "1", symbol: "VCB" })])

    renderNews(<OpenArticle article="VCB:1" />)

    expect(screen.getByRole("button", { name: "VCB" })).toBeInTheDocument()
  })
})

describe("the reading column, with no article to read", () => {
  it("blames the request, not the feed's contents, when the feed failed", () => {
    feed.isError = true

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByText("Chưa đọc được bài viết.")).toBeInTheDocument()
    expect(screen.queryByText("Bài viết không còn trong bảng tin.")).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }))
    expect(feed.refetch).toHaveBeenCalledTimes(1)
  })

  it("says the article has left the feed when the feed itself loaded", () => {
    feed.data = response([])

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByText("Bài viết không còn trong bảng tin.")).toBeInTheDocument()
  })

  it("offers the way back out of both dead ends", () => {
    feed.isError = true

    renderNews(<OpenArticle article="chung-khoan:1" />)

    expect(screen.getByRole("button", { name: /Trở về tin tức/ })).toBeInTheDocument()
  })
})

describe("the rail's disclosure card", () => {
  it("lists the selected company's filings, and says they are not press articles", () => {
    feed.data = response([item({ id: "1" })])
    companyNews.data = {
      symbol: "VCB",
      items: [
        {
          id: "9001",
          title: "Nghị quyết HĐQT về phương án phát hành",
          source: "VCI",
          published_at: "2026-08-14 09:30",
          summary: null,
          content: null,
          url: null,
          image_url: null,
          category: null,
          price: null,
          price_change_pct: null,
        },
      ],
      total_count: 1,
    }

    renderNews(<NewsView />)

    expect(screen.getByText("Nghị quyết HĐQT về phương án phát hành")).toBeInTheDocument()
    expect(screen.getByText("14/08/2026")).toBeInTheDocument()
    expect(screen.getByText(/không phải bài báo/)).toBeInTheDocument()
    // Nothing to open, so nothing that looks openable.
    expect(
      screen.queryByRole("button", { name: /Nghị quyết HĐQT/ }),
    ).not.toBeInTheDocument()
  })
})
