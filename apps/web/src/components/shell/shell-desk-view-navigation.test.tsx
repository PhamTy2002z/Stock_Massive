// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ShellProvider, useShell } from "./shell-state"

afterEach(cleanup)

let shell: ReturnType<typeof useShell>

function Probe() {
  shell = useShell()
  return null
}

describe("opening a Signal Desk card from the transcript", () => {
  it("enters the desk and folds the sidebar even on a wide viewport", () => {
    render(
      <ShellProvider>
        <Probe />
      </ShellProvider>,
    )

    act(() => shell.dispatch({ type: "viewport", width: 1664 }))
    expect(shell.state.sidebarOpen).toBe(true)

    act(() =>
      shell.dispatch({ type: "open-desk-view", artifactId: "artifact-3" }),
    )

    expect(shell.state.signalDesk).toBe(true)
    expect(shell.state.sidebarOpen).toBe(false)
    expect(shell.state.inspector).toBe("deskView")
    expect(shell.state.deskViewArtifactId).toBe("artifact-3")
  })
})
