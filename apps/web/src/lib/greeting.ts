import type { PartOfDay } from "./market-session"

/**
 * One opening line, given whoever is reading it.
 *
 * A name is not guaranteed — an account can exist without a full name — so
 * every line has to read as a finished sentence without one.
 */
export type GreetingLine = (name: string | null) => string

/**
 * `Rise and shine, Phạm Phước Tỷ`, and just `Rise and shine` when the account
 * has no name to use. `tail` is punctuation that has to land after the name
 * rather than after the phrase: `Coffee first, <name>?`, never `Coffee first?,
 * <name>`.
 */
const named =
  (phrase: string, tail = ""): GreetingLine =>
  (name) =>
    `${phrase}${name ? `, ${name}` : ""}${tail}`

/** A line that is already a whole joke; a name wedged into it would break it. */
const solo =
  (line: string): GreetingLine =>
  () =>
    line

/**
 * What the new-conversation screen can open with, by where the day is on the
 * market's clock.
 *
 * **Index 0 of every list is the plain form**, and the screen leans on that:
 * it is what renders before the browser knows who is reading, so the line the
 * server sends is the same neutral greeting this product has always opened on.
 * The rest are picked from at random once the session resolves.
 *
 * These lines are the only English in the product — see the note on `Greeting`
 * in `components/shell/view-new`. Keeping them light is the point, but none of
 * them claims anything about the market itself: a desk that exists to keep
 * numbers provable should not open on a quip that is wrong at 11:45.
 */
export const GREETINGS: Record<PartOfDay, GreetingLine[]> = {
  Morning: [
    named("Morning"),
    named("Rise and shine"),
    named("Coffee first", "?"),
    named("Look who's up"),
    named("Fresh start"),
    solo("Hello, early bird"),
  ],
  Afternoon: [
    named("Afternoon"),
    named("Back at it"),
    named("Survived lunch"),
    named("Still going strong"),
    named("Hello again"),
    solo("Afternoon, deskmate"),
  ],
  Evening: [
    named("Evening"),
    named("Burning the candle", "?"),
    named("Late shift"),
    named("Winding down"),
    named("Off the clock"),
    solo("Hello, night owl"),
  ],
}

/**
 * The plain greeting: the one line that is safe to render before the browser
 * has told us anything.
 */
export function plainGreeting(partOfDay: PartOfDay, name: string | null): string {
  return GREETINGS[partOfDay][0](name)
}

/**
 * One of the day's lines, chosen by `roll`.
 *
 * The roll is passed in rather than drawn here so the caller owns *when* the
 * dice are thrown. That matters: a `Math.random()` inside this function would
 * be called once on the server and again during hydration, and the two answers
 * would not agree.
 *
 * @param roll Any number in `[0, 1)` — `Math.random()`'s own range.
 */
export function greetingFor(
  partOfDay: PartOfDay,
  name: string | null,
  roll: number,
): string {
  const lines = GREETINGS[partOfDay]
  const index = Math.min(Math.floor(roll * lines.length), lines.length - 1)
  return lines[index](name)
}
