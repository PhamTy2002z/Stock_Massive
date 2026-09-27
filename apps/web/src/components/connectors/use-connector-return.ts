"use client"

import { useEffect } from "react"

import { useShell } from "@/components/shell/shell-state"
import {
  readOAuthReturn,
  requestConnectorsPane,
  stripOAuthReturn,
} from "@/lib/connectors/open-pane"

/**
 * Coming back from an OAuth sign-in: open Settings › Kết nối and say how it went.
 *
 * The query is stripped at once so a reload does not report it twice. The
 * overlay is opened on the next task rather than in this effect: the shell's
 * own mount effect restores the view from the URL, and a view change closes
 * every overlay — it runs after this one (parents' effects follow children's),
 * so dispatching now would be undone in the same commit.
 */
export function useConnectorReturn(): void {
  const { dispatch } = useShell()
  useEffect(() => {
    const request = readOAuthReturn(window.location.search)
    if (!request) return
    window.history.replaceState(window.history.state, "", stripOAuthReturn(window.location.href))
    requestConnectorsPane(request)
    // Not cleared on cleanup: the URL is already stripped, so a StrictMode
    // re-run finds nothing and the one scheduled open is the only one.
    setTimeout(() => dispatch({ type: "overlay", overlay: "settings" }), 0)
  }, [dispatch])
}
