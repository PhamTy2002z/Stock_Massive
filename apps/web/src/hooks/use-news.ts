"use client"

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import {
  fetchCompanyNews,
  fetchNewsArticle,
  fetchNewsCategories,
  fetchNewsFeed,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { STALE_TIME } from "@/lib/query-config"

/**
 * One facet of the press feed, refreshed when the reader comes back.
 *
 * Keyed on the category, because switching pills asks the API a different
 * question — one key for all of them would answer the new pill out of the old
 * pill's cache. `keepPreviousData` is the other half of that: the column keeps
 * showing the facet it has while the next one is in flight, rather than blanking
 * between two presses.
 *
 * `FREQUENT` rather than `STATIC` because this is a wire now. CafeF publishes
 * through the day, so five minutes of staleness is five minutes of a reader
 * looking at a feed that has moved on; a minute is still far short of a poll.
 */
export function useNewsFeed(category: string) {
  const query = useQuery({
    queryKey: queryKeys.newsFeed(category),
    queryFn: () => fetchNewsFeed(category),
    staleTime: STALE_TIME.FREQUENT,
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: true,
    // The provider's default sends a refused request to the ErrorBoundary,
    // which for this query would replace the whole shell — the conversation and
    // the board included — because one pane of headlines came back 404 or spent
    // its quota. News is a view, not the app: the feed reports its own failure
    // and offers its own retry, which is also what passing the non-veiling
    // fetch behaviour already promised.
    throwOnError: false,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isError: query.isError,
    isFetching: query.isFetching,
    dataUpdatedAt: query.dataUpdatedAt,
    refetch: query.refetch,
  }
}

/**
 * The facets on offer, as the API's own registry.
 *
 * Its own query rather than a field read off the feed, so the pill row survives
 * the feed failing: the reader whose facet returned nothing still needs a way to
 * ask for a different one. A registry changes on a deploy, not on a publish,
 * hence `STATIC`.
 */
export function useNewsCategories() {
  const query = useQuery({
    queryKey: queryKeys.newsCategories,
    queryFn: fetchNewsCategories,
    staleTime: STALE_TIME.STATIC,
    // Same reasoning as the feed: a missing registry costs the reader a pill
    // row, and must not cost them the application.
    throwOnError: false,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isError: query.isError,
  }
}

/**
 * The body of the article the reader has open, fetched on the way in.
 *
 * `null` while no article is open, which is what `enabled` reads: the reading
 * column is one view of a shell that spends most of its life on the feed, and a
 * query that fired anyway would ask CafeF for a story nobody opened.
 *
 * `STATIC` because a published article does not change. Backing out to the feed
 * and pressing the same headline again is a cache hit, not a second fetch — and
 * that matters more here than on the other queries, since a miss costs the API
 * a request to the publisher rather than a read of its own store.
 */
export function useNewsArticle(url: string | null) {
  const query = useQuery({
    queryKey: queryKeys.newsArticle(url ?? ""),
    queryFn: () => fetchNewsArticle(url as string),
    enabled: url !== null,
    staleTime: STALE_TIME.STATIC,
    // The article still has its headline, its summary and a link to the
    // original when the body refuses. Losing the body is a degraded read, and
    // the column says so itself rather than surrendering the shell to the
    // ErrorBoundary.
    throwOnError: false,
  })

  return {
    data: query.data,
    isPending: url !== null && query.isPending,
    isError: query.isError,
    refetch: query.refetch,
  }
}

/**
 * One symbol's corporate disclosures — a different source from the feed above.
 *
 * These are VCI filings, not press articles: titles and dates, with no body to
 * open. The rail lists them beside the press feed precisely so the two stay
 * visibly distinct. Disclosures land a few times a week, so `STATIC`.
 */
export function useCompanyNews(symbol: string) {
  const query = useQuery({
    queryKey: queryKeys.companyNews(symbol),
    queryFn: () => fetchCompanyNews(symbol),
    staleTime: STALE_TIME.STATIC,
    // A rail card, and never a reason to veil the screen it sits beside.
    throwOnError: false,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isError: query.isError,
  }
}
