// @vitest-environment jsdom
/**
 * The attachment path through the surface: choose, see, remove, send, redraw.
 *
 * The chip and the composer are tested against a stubbed desk, because what is
 * under test there is drawing and pressing. The parts with a real decision in
 * them — which ids a question carries, what a retry sends, whether an object URL
 * is released — are tested against the real handlers.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { AttachmentChip, readableSize } from "./attachment-chip"
import { ATTACHMENT_COPY, attachmentRefusal } from "@/lib/alpha-desk/copy"
import { attachmentUrl } from "@/lib/alpha-desk/api"

afterEach(cleanup)

describe("how a file's size reads", () => {
  it("stays in bytes below a kilobyte", () => {
    expect(readableSize(512)).toBe("512 B")
  })

  it("rounds to whole kilobytes, then to tenths of a megabyte", () => {
    expect(readableSize(2_048)).toBe("2 KB")
    expect(readableSize(3_500_000)).toBe("3.3 MB")
  })
})

describe("one attachment chip", () => {
  it("names the file and shows what it weighs", () => {
    render(
      <AttachmentChip filename="bang-gia.png" byteSize={2_048} image={false} />,
    )

    expect(screen.getByText("bang-gia.png")).toBeInTheDocument()
    expect(screen.getByText("2 KB")).toBeInTheDocument()
  })

  it("draws the picture rather than an icon when there is one", () => {
    const { container } = render(
      <AttachmentChip
        filename="anh.png"
        byteSize={10}
        image
        previewUrl="blob:preview"
      />,
    )

    expect(container.querySelector("img")).toHaveAttribute("src", "blob:preview")
  })

  it("says it is still uploading instead of stating a size it does not know", () => {
    render(
      <AttachmentChip filename="a.png" byteSize={0} image={false} status="uploading" />,
    )

    expect(screen.getByText(ATTACHMENT_COPY.uploading)).toBeInTheDocument()
  })

  it("shows the reason it failed, in the product's own words", () => {
    render(
      <AttachmentChip
        filename="qua-lon.png"
        byteSize={0}
        image={false}
        status="error"
        error={attachmentRefusal("file_too_large")}
      />,
    )

    expect(screen.getByText(ATTACHMENT_COPY.refusals.file_too_large)).toBeInTheDocument()
  })

  it("offers no way to remove a file from a question already asked", () => {
    render(<AttachmentChip filename="cu.png" byteSize={10} image={false} />)

    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("takes one file back off a question not yet sent", () => {
    const onRemove = vi.fn()
    render(
      <AttachmentChip filename="moi.png" byteSize={10} image={false} onRemove={onRemove} />,
    )

    fireEvent.click(
      screen.getByRole("button", { name: ATTACHMENT_COPY.remove("moi.png") }),
    )

    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})

describe("what a refusal says", () => {
  it("names the action left to take for each reason the backend sends", () => {
    expect(attachmentRefusal("file_too_large")).toContain("nhỏ hơn")
    expect(attachmentRefusal("turn_image_budget")).toContain("bỏ một ảnh")
  })

  it("still says something for a reason this build has never heard of", () => {
    // A blank space beside a file that did not upload is the one outcome with no
    // reading at all.
    expect(attachmentRefusal("something_new")).toBe(ATTACHMENT_COPY.refusals.unknown)
    expect(attachmentRefusal(null)).toBe(ATTACHMENT_COPY.refusals.unknown)
  })
})

describe("where an attachment's bytes come from", () => {
  it("goes through the proxy, with the id escaped", () => {
    expect(attachmentUrl("abc-123")).toBe("/api/alpha-desk/attachments/abc-123")
    expect(attachmentUrl("a/b")).toBe("/api/alpha-desk/attachments/a%2Fb")
  })
})

describe("the object URL a local preview holds", () => {
  it("is released when the chip goes away", async () => {
    // The leak this prevents: a reader who attaches and removes twenty
    // screenshots while writing one question would otherwise pin all twenty in
    // memory for the life of the tab.
    const created: string[] = []
    const revoked: string[] = []
    const create = vi
      .spyOn(URL, "createObjectURL")
      .mockImplementation(() => {
        const url = `blob:${created.length}`
        created.push(url)
        return url
      })
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation((url: string) => void revoked.push(url))

    const { useObjectUrl } = await import("./attachment-chip")
    function Holder({ file }: { file: File | null }) {
      const url = useObjectUrl(file)
      return <span data-testid="url">{url ?? "none"}</span>
    }

    const file = new File(["x"], "a.png", { type: "image/png" })
    const view = render(<Holder file={file} />)
    await waitFor(() => expect(screen.getByTestId("url")).toHaveTextContent("blob:0"))

    view.unmount()

    await waitFor(() => expect(revoked).toEqual(["blob:0"]))
    create.mockRestore()
    revoke.mockRestore()
  })
})
