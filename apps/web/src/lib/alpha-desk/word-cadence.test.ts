/**
 * Whether prose can be split into animatable words without losing any of it.
 *
 * One property, and it is the one that is invisible in a screenshot: the words
 * and the whitespace put back together are the text that went in. A character
 * dropped here is a character missing from an answer, and nothing downstream
 * would ever notice.
 */

import { describe, expect, it } from "vitest"

import { CHUNK_CLASS, rehypeWordCadence, wrapWords } from "./word-cadence"

interface Node {
  type: string
  tagName?: string
  value?: string
  properties?: Record<string, unknown>
  children?: Node[]
}

function text(value: string): Node {
  return { type: "text", value }
}

function element(tagName: string, children: Node[]): Node {
  return { type: "element", tagName, properties: {}, children }
}

/** Every character the tree would render, words and whitespace alike. */
function rendered(node: Node): string {
  if (node.type === "text") return node.value ?? ""
  return (node.children ?? []).map(rendered).join("")
}

/** Every word element, in the order a reader meets them. */
function words(node: Node): Node[] {
  const own = node.type === "element" && node.tagName === "span" ? [node] : []
  return [...own, ...(node.children ?? []).flatMap(words)]
}

describe("splitting prose into words", () => {
  it("gives back every character it was handed", () => {
    const value = "STB tăng nhẹ 0,27%\ntrong phiên chiều.  "

    expect(wrapWords(value).map((node) => rendered(node as Node)).join("")).toBe(value)
  })

  it("wraps the words and leaves the whitespace as it found it", () => {
    const nodes = wrapWords("hai từ") as Node[]

    expect(nodes.map((node) => node.type)).toEqual(["element", "text", "element"])
    expect(nodes[1].value).toBe(" ")
    expect(nodes[0].properties?.className).toEqual([CHUNK_CLASS])
  })

  it("wraps every word of a tree, through the elements in it", () => {
    const tree: Node = {
      type: "root",
      children: [element("p", [text("một "), element("strong", [text("hai ba")])])],
    }

    rehypeWordCadence()(tree)

    expect(words(tree).map(rendered)).toEqual(["một", "hai", "ba"])
    expect(rendered(tree)).toBe("một hai ba")
  })

  it("writes no moment onto a word, because the pacer decides that", () => {
    // A word fades in when it mounts, and what mounts it is the revealed prefix
    // growing. An `animation-delay` here would mean text laid out before it is
    // visible, which is height the transcript's pin cannot absorb.
    const tree: Node = { type: "root", children: [element("p", [text("một hai")])] }

    rehypeWordCadence()(tree)

    expect(words(tree).map((word) => word.properties?.style)).toEqual([undefined, undefined])
  })

  it("leaves code alone, because its whitespace is content", () => {
    const tree: Node = {
      type: "root",
      children: [element("pre", [element("code", [text("def f(x):\n    return x")])])],
    }

    rehypeWordCadence()(tree)

    expect(words(tree)).toHaveLength(0)
    expect(rendered(tree)).toBe("def f(x):\n    return x")
  })
})
