"use client";

/**
 * Agentation is a UI-annotation devtool for AI coding agents — useful only
 * while a developer has the app open in dev. Wrapped in
 * `dynamic(..., { ssr: false })` so the module never lands in the server
 * bundle, and gated on `NODE_ENV` so Next dead-code-eliminates this whole
 * branch at production `next build`.
 *
 * No props passed: the default `copyToClipboard=true` is exactly the
 * copy-then-paste-into-agent-chat loop the package's own docs describe.
 */
import dynamic from "next/dynamic";

const Agentation = dynamic(
  () => import("agentation").then((m) => m.Agentation),
  { ssr: false },
);

export function AgentationToolbar() {
  if (process.env.NODE_ENV === "production") return null;
  return <Agentation />;
}
