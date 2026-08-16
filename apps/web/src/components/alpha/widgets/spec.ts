/**
 * The second half of ADR-0012's double validation.
 *
 * `apps/api` validated the selection before it stored it. This validates the
 * stored spec again *before* the registry is asked for a component, and the
 * reason is not distrust of the backend: a message is kept indefinitely, and
 * the build reading it a year from now is not the build that wrote it. A spec
 * written under a version this bundle no longer ships is not corrupt, it is
 * old — and the difference between missing it cleanly and throwing inside the
 * transcript is this function.
 *
 * Everything below returns `null` rather than raising. A thrown error in a
 * transcript takes the text answer down with it, and the text answer is the
 * part the reader actually needs.
 */

import { WIDGET_NAMES, type WidgetName, type WidgetRefusal, type WidgetSpec } from "./types"

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stringArray(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null
  return value.every((item) => typeof item === "string") ? (value as string[]) : null
}

export function parseWidgetSpec(value: unknown): WidgetSpec | null {
  if (!isRecord(value)) return null

  const name = value.name
  if (typeof name !== "string") return null
  if (!(WIDGET_NAMES as readonly string[]).includes(name)) return null

  const version = value.version
  // An integer, because the registry is keyed on one. A float here is a spec
  // written by something that is not this system.
  if (typeof version !== "number" || !Number.isInteger(version)) return null

  const title = value.title
  const asOf = value.as_of
  const descriptorId = value.descriptor_id
  if (
    typeof title !== "string" ||
    typeof asOf !== "string" ||
    typeof descriptorId !== "string" ||
    !asOf ||
    !descriptorId
  ) {
    return null
  }

  const fields = stringArray(value.fields)
  const toolCallIds = stringArray(value.tool_call_ids)
  if (fields === null || toolCallIds === null) return null

  const descriptor = value.descriptor
  if (!isRecord(descriptor)) return null
  // A descriptor with no kind cannot be resolved, and resolving it wrongly is
  // worse than not drawing it.
  if (typeof descriptor.kind !== "string") return null

  const unit = value.unit
  if (unit !== null && typeof unit !== "string") return null

  return {
    name: name as WidgetName,
    version,
    title,
    fields,
    unit: unit ?? null,
    as_of: asOf,
    descriptor,
    descriptor_id: descriptorId,
    tool_call_ids: toolCallIds,
    requested: value.requested === true,
  }
}

/** Every spec on a message that this build can still make sense of. */
export function parseWidgetSpecs(value: unknown): WidgetSpec[] {
  if (!Array.isArray(value)) return []
  return value
    .map(parseWidgetSpec)
    .filter((spec): spec is WidgetSpec => spec !== null)
}

export function parseWidgetRefusals(value: unknown): WidgetRefusal[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.code !== "string") return []
    const link = item.deep_link
    // Only a refusal with somewhere to send the reader is worth rendering; the
    // backend already dropped the rest, and this is the belt to that braces.
    if (typeof link !== "string" || !link.startsWith("/")) return []
    return [{ code: item.code, deep_link: link }]
  })
}
