"use client";

/**
 * The dev-only mount point for the canvas fixture.
 *
 * Split from the fixture itself for the reason `agentation-toolbar.tsx` is a
 * separate file: the fixture imports a JSON payload of several thousand cells,
 * and a static import anywhere on the render path would put it in the
 * production bundle whatever the `NODE_ENV` check said. Behind
 * `dynamic(..., { ssr: false })` the branch is dead code at `next build` and
 * the payload is never asked for.
 */
import dynamic from "next/dynamic";

const CanvasFixture = dynamic(
  () => import("./canvas-fixture").then((m) => m.CanvasFixture),
  { ssr: false },
);

export function CanvasFixtureToolbar() {
  if (process.env.NODE_ENV === "production") return null;
  return <CanvasFixture />;
}
