"use client"

import { ArrowUpRight } from "lucide-react"

import { SourceIcon } from "@/components/alpha/message/source-icon"
import { safeHref } from "@/components/alpha/message/source-list"
import { answerSources, type AnswerSource } from "@/lib/alpha-desk/answer-sources"

import { useDeskTranscript } from "./desk-state"
import { useShell } from "./shell-state"

/**
 * Everything one answer rested on, one row per source, each row a link.
 *
 * A plain list (owner decision, 2026-09-27): who published it, what it was,
 * and a click that opens it. The work that found them — the searches and reads,
 * in order — is the timeline above the answer, not this panel.
 *
 * It reads the transcript rather than holding its own copy, so a message that
 * is refetched keeps one version of itself and this panel cannot drift from it.
 *
 * Every title here was written by a provider or a page, not by this product, so
 * it is printed as plain text and only an `http:`/`https:` link is clickable.
 * A link's host is printed beside its publisher, so a label cannot pass one
 * domain off as another.
 */
export function SourcesTab() {
  const { state } = useShell()
  const desk = useDeskTranscript()

  const entry = desk.entries.find(
    (candidate) =>
      candidate.kind === "assistant" && candidate.messageId === state.sourcesMessageId,
  )

  if (entry === undefined || entry.kind !== "assistant") {
    return (
      <p className="px-1 py-2 text-meta text-muted-foreground">
        This answer is no longer in the open conversation.
      </p>
    )
  }

  const sources = answerSources(entry.view.text, entry.view.toolCalls)
  if (sources.length === 0) {
    return (
      <p className="px-1 py-2 text-meta text-muted-foreground">
        This answer doesn't rest on any source.
      </p>
    )
  }

  return (
    <ul className="grid gap-1">
      {sources.map((source, index) => (
        <li key={`${source.url ?? source.title}-${index}`}>
          <SourceRow source={source} />
        </li>
      ))}
    </ul>
  )
}

function SourceRow({ source }: { source: AnswerSource }) {
  const href = source.url === null ? null : safeHref(source.url)

  const body = (
    <>
      <SourceIcon source={source.mark} favicon={source.favicon} size={20} className="mt-0.5" />
      <span className="grid min-w-0 flex-1 gap-0.5">
        <span className="truncate text-meta font-medium text-ink-1">
          {source.publisher}
          {/* Where the link goes, beside who it claims to be from: the name is
              the answer's word, the host is the link's. Left off when the two
              already say the same thing. */}
          {href !== null &&
            source.host !== null &&
            source.host.toLowerCase() !== source.publisher.toLowerCase() && (
              <span className="font-normal text-muted-foreground"> · {source.host}</span>
            )}
        </span>
        <span className="text-pretty text-micro text-muted-foreground">{source.title}</span>
      </span>
      {href !== null && (
        <ArrowUpRight className="mt-0.5 size-[15px] flex-none text-muted-foreground" strokeWidth={1.6} />
      )}
    </>
  )

  if (href === null) return <div className="flex items-start gap-3 px-2 py-2.5">{body}</div>

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className="flex items-start gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-accent"
    >
      {body}
    </a>
  )
}
