"use client"

import { useCallback, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  acceptConnectorChanges,
  addConnector,
  deleteConnector,
  fetchConnectors,
  refreshConnector,
  safeAuthorizeUrl,
  setToolAccess,
  setToolAction,
  startConnectorOAuth,
  updateConnector,
} from "@/lib/connectors/api"
import { refusalMessage } from "@/lib/connectors/copy"
import type {
  AddConnectorInput,
  Connector,
  ConnectorsState,
  ConnectorTool,
  ToolAccess,
  ToolAction,
} from "@/lib/connectors/types"
import { queryKeys } from "@/lib/query-keys"

/**
 * The connectors resource and every write to it.
 *
 * Each write answers with the connector as it now stands, and that answer
 * replaces the cached copy — no refetch, and no optimistic guess the server
 * might refuse (a write tool set to `allow` is exactly such a refusal).
 *
 * `busy` names the write in flight so only its own control shows it; `error`
 * is the last refusal in the reader's words. Both are per caller: the composer
 * menu and the Settings pane do not share a spinner.
 */
export function useConnectors() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: queryKeys.connectors, queryFn: fetchConnectors })
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const update = useCallback(
    (change: (state: ConnectorsState) => ConnectorsState) =>
      client.setQueryData<ConnectorsState>(queryKeys.connectors, (state) =>
        state ? change(state) : state,
      ),
    [client],
  )

  const put = useCallback(
    (connector: Connector) =>
      update((state) => ({
        ...state,
        connectors: state.connectors.some((one) => one.id === connector.id)
          ? state.connectors.map((one) => (one.id === connector.id ? connector : one))
          : [...state.connectors, connector],
      })),
    [update],
  )

  const run = useCallback(async <T,>(key: string, op: () => Promise<T>): Promise<T | undefined> => {
    setBusy(key)
    setError(null)
    try {
      return await op()
    } catch (cause) {
      setError(refusalMessage(cause))
      return undefined
    } finally {
      setBusy(null)
    }
  }, [])

  const signIn = useCallback(
    (id: string) =>
      run(`oauth:${id}`, async () => {
        const { authorize_url } = await startConnectorOAuth(id)
        const target = safeAuthorizeUrl(authorize_url)
        if (!target) throw new Error("no authorize url")
        window.location.assign(target)
      }),
    [run],
  )

  return {
    state: query.data,
    isPending: query.isPending,
    isError: query.isError,
    refetch: query.refetch,
    busy,
    error,
    clearError: useCallback(() => setError(null), []),

    add: useCallback(
      (input: AddConnectorInput) =>
        run("add", async () => {
          const connector = await addConnector(input)
          put(connector)
          return connector
        }),
      [run, put],
    ),

    setEnabled: useCallback(
      (id: string, enabled: boolean) =>
        run(`enabled:${id}`, async () => put(await updateConnector(id, { enabled }))),
      [run, put],
    ),

    setHeader: useCallback(
      (id: string, headerValue: string) =>
        run(`header:${id}`, async () => put(await updateConnector(id, { header_value: headerValue }))),
      [run, put],
    ),

    setTool: useCallback(
      (id: string, tool: string, action: ToolAction) =>
        run(`tool:${id}:${tool}`, async () => put(await setToolAction(id, tool, action))),
      [run, put],
    ),

    /**
     * One action for a whole group, skipping tools that cannot take it or
     * already have it. Sequential, so the last answer is the whole truth.
     */
    setGroup: useCallback(
      (id: string, tools: ConnectorTool[], action: ToolAction) =>
        run(`group:${id}`, async () => {
          for (const tool of tools) {
            if (tool.action === action || !tool.allowed_actions.includes(action)) continue
            put(await setToolAction(id, tool.name, action))
          }
        }),
      [run, put],
    ),

    refresh: useCallback(
      (id: string) => run(`refresh:${id}`, async () => put(await refreshConnector(id))),
      [run, put],
    ),

    accept: useCallback(
      (id: string) => run(`accept:${id}`, async () => put(await acceptConnectorChanges(id))),
      [run, put],
    ),

    remove: useCallback(
      (id: string) =>
        run(`remove:${id}`, async () => {
          await deleteConnector(id)
          update((state) => ({ ...state, connectors: state.connectors.filter((one) => one.id !== id) }))
          return true
        }),
      [run, update],
    ),

    setAccess: useCallback(
      (mode: ToolAccess) =>
        run("access", async () => {
          const { tool_access } = await setToolAccess(mode)
          update((state) => ({ ...state, tool_access }))
        }),
      [run, update],
    ),

    signIn,
  }
}
