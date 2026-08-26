"use client";

/**
 * Agentation là devtool annotate UI cho AI coding agent — chỉ có ích lúc
 * developer đang mở app trong dev. Bọc bằng `dynamic(..., { ssr: false })`
 * để module không nằm trên server bundle, và gate bằng `NODE_ENV` để Next
 * dead-code-eliminate toàn bộ nhánh này ở `next build` production.
 *
 * Không truyền prop: default `copyToClipboard=true` là đúng loop copy →
 * paste vào chat agent mà tài liệu package mô tả.
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
