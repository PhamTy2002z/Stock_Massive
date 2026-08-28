# Scout — web chat shell (read-only)

Ngày 2026-08-27. Phạm vi: `apps/web/src/components/shell/` (17 file) + surface liên quan
(`components/alpha/message/*`, `components/canvas/*`, `hooks/*`, `lib/greeting.ts`,
`app/layout.tsx`, `tailwind.config.js`, `app/globals.css`, `components/dev/*`).
Không sửa file nào. Mọi claim kèm `path:line`.

---

## 1. Cây component

Entry: `src/app/page.tsx:18` → `<Suspense><AppShell /></Suspense>`, `dynamic = "force-dynamic"`
(`src/app/page.tsx:11`).

```
AppShell                          shell/app-shell.tsx:22   (66 dòng)
└─ ShellProvider                  shell/shell-state.tsx:316 (427 dòng)
   └─ DeskProvider                shell/desk-state.tsx:83   (392 dòng)
      └─ Frame                    shell/app-shell.tsx:32
         ├─ scrim overlay         app-shell.tsx:37-44  (account|attach|thread)
         ├─ Sidebar               shell/sidebar.tsx:38  (467 dòng)
         │  ├─ VisgniteWordmark   shared/visgnite-logo
         │  ├─ IconButton ×2      primitives.tsx:80    (thu gọn / tìm hội thoại)
         │  ├─ Nav                sidebar.tsx:84  → NavRow  sidebar.tsx:111
         │  ├─ Conversations      sidebar.tsx:171
         │  │  ├─ SectionLabel    sidebar.tsx:147
         │  │  ├─ ThreadRow       sidebar.tsx:228
         │  │  │  ├─ ThreadMenu   sidebar.tsx:367
         │  │  │  └─ RenameField  sidebar.tsx:420
         │  │  └─ QuietLine       primitives.tsx:260
         │  └─ AccountMenu        shell/account-menu.tsx:28 (123 dòng)
         │     └─ Avatar          account-menu.tsx:114
         ├─ main
         │  ├─ TopBar             shell/top-bar.tsx:20  (101 dòng)
         │  │  └─ Menu/MenuItem   primitives.tsx:106,127
         │  └─ ChatView           shell/view-chat.tsx:117 (560 dòng)
         │     ├─ Greeting        view-chat.tsx:98
         │     ├─ Composer        shell/composer.tsx:72  (276 dòng)
         │     │  ├─ WaveformIcon composer.tsx:35
         │     │  └─ AttachMenu   composer.tsx:236
         │     ├─ UserMessage     view-chat.tsx:486
         │     ├─ AssistantMessage alpha/message/assistant-message.tsx:39 (170)
         │     └─ DraftMessage    alpha/message/draft-message.tsx:34 (121)
         ├─ Inspector             shell/inspector.tsx:53 (142 dòng)
         │  ├─ SourcesTab         shell/sources-tab.tsx:43 (256 dòng)
         │  └─ CanvasPanel        canvas/canvas-panel.tsx:41 (141) — next/dynamic, ssr:false
         └─ Overlays              shell/overlays.tsx:23 (299 dòng)
            ├─ CommandPalette     overlays.tsx:119
            ├─ ShareDialog        overlays.tsx:203
            ├─ SettingsDialog     shell/settings-dialog.tsx (158 dòng)
            └─ Scrim              overlays.tsx:38 (focus trap)
```

Test file trong `shell/`: `shell.test.tsx` (613), `sources-tab.test.tsx` (167),
`thread-menu.test.tsx` (188), `view-chat-pin.test.tsx` (221).
Không dùng: `hooks/use-mobile.tsx:5` (`useIsMobile` không có importer).

---

## 2. State management

| State | Nơi giữ | Ghi chú |
|---|---|---|
| sidebar open, inspector tab/width, overlay, viewport, draft, contextSymbol | reducer `reduce` `shell-state.tsx:197` | `ShellState` `shell-state.tsx:51-112` |
| threadId, entries, canCancel, refusal, flag/helpful | context `DeskProvider` `desk-state.tsx:83` | `DeskApi` `desk-state.tsx:56-79` |
| menu mở / row đang rename | local state `sidebar.tsx:173-174` | singular, giữ ở `Conversations` |

**Đóng sidebar dưới 768px** — trong reducer, không dùng effect:

```ts
case "viewport":
  if (action.width < 768) return { ...state, viewport: action.width, sidebarOpen: false }
  return foldSidebarIfCramped({ ...state, viewport: action.width })
```
`shell-state.tsx:288-290`. Viewport đo sau mount qua `resize` listener `shell-state.tsx:336-341`
(0 trước đó, `shell-state.tsx:90`). Một chiều: co xuống <768 thì đóng, nới ra **không** tự mở lại.

`foldSidebarIfCramped` `shell-state.tsx:188-195`: mở inspector mà `viewport - inspectorWidth -
SIDEBAR_WIDTH < CONVERSATION_MIN (520)` thì gập sidebar. Hằng số: `SIDEBAR_WIDTH = 274`
`shell-state.tsx:141`, `INSPECTOR_DEFAULT = 408`, `INSPECTOR_MIN = 320` `:142-143`.

**Layout sidebar = flex row + wrapper co width**, không fixed:
`app-shell.tsx:36` `div.relative.flex.h-dvh.overflow-hidden` → `sidebar.tsx:42-46` wrapper
`flex-none overflow-hidden transition-[width]`, `style={{ width: open ? 274 : 0 }}`;
`aside` bên trong giữ cứng 274px + `-translate-x-4 opacity-0` khi đóng (`sidebar.tsx:47-55`).
Inspector thì **fixed**: `inspector.tsx:71` `fixed right-0 top-0 z-20`, và `main` bù bằng
`paddingRight: panelWidth` (`app-shell.tsx:49`) — trừ compact <768 thì padding 0 và inspector
`width:100%` (`inspector.tsx:57,69`).

Keyboard toàn cục `shell-state.tsx:345-364`: Escape đóng overlay + đóng inspector; ⌘/Ctrl+K mở
palette; ⇧⌘, (match `event.code === "Comma"`) mở settings.

---

## 3. Empty state + Greeting

`view-chat.tsx:306-317` — điều kiện `desk.threadId === null && desk.entries.length === 0`:
một div căn giữa `max-w-[680px]` chứa `<Greeting />` + `<Composer variant="opening" />`.
Không có suggestion chip, không có example prompt, không có onboarding.

`Greeting` `view-chat.tsx:98-115`: `VisgniteMark` + `h2.font-serif` cỡ
`clamp(1.6rem,2.7vw,2.15rem)`, màu `text-ink-display`.

Chuỗi "Evening" **hardcode tiếng Anh**, không i18n: `lib/greeting.ts:42-67` bảng
`GREETINGS: Record<PartOfDay, GreetingLine[]>` — Morning/Afternoon/Evening, mỗi nhóm 6 dòng
("Evening", "Burning the candle?", "Late shift", "Winding down", "Off the clock",
"Hello, night owl"). Index 0 là dạng plain (`plainGreeting` `greeting.ts:73`), dạng random
`greetingFor` `greeting.ts:87`. Part-of-day theo giờ VN: `<12 Morning`, `<17 Afternoon`,
còn lại `Evening` — `lib/market-session.ts:134-139`. Roll bốc một lần mỗi mount
(`view-chat.tsx:100`), gate trên `isPending` của `useAuth` để hydration khớp
(`view-chat.tsx:103-105`). Comment trong `greeting.ts:38-40` tự nhận đây là **chỗ duy nhất còn
tiếng Anh trong sản phẩm** — và trỏ tới `components/shell/view-new`, file **đã bị xoá** (stale).

---

## 4. Composer (`shell/composer.tsx`)

| Mục | Chi tiết |
|---|---|
| Nút gửi | `WaveformIcon` — SVG 5 vạch tự vẽ, `composer.tsx:35-54`; button `size-[34px] rounded-full bg-foreground text-background`, `composer.tsx:214`; `sr-only` label `SEND_LABEL` `composer.tsx:217` |
| Khi Turn đang chạy | đổi sang nút "Dừng" (`Square` icon) `composer.tsx:186-195` |
| "Visgnite Pro" dòng 182 | `<span>` **tĩnh, không phải button**, `composer.tsx:182-185` — chỉ text + `ChevronDown`, `hidden … md:flex`; giả model-picker chưa nối gì |
| Attach menu | `AttachMenu` `composer.tsx:236-276` — **7 item, cả 7 `disabled`**: Thêm tệp hoặc ảnh (hint ⌘U) · Chụp màn hình bảng giá · Thêm vào danh mục · Mẫu phân tích · Nguồn dữ liệu kết nối · Nghiên cứu sâu · Tra tin tức thị trường; 2 `MenuSeparator` |
| Enter / Shift+Enter | `onKeyDown` `composer.tsx:113-118`: Enter (không Shift) → preventDefault + submit; Shift+Enter → xuống dòng mặc định |
| ⌘K | **không** ở composer; ở listener toàn cục `shell-state.tsx:351-354` → mở palette |
| ⌘U | chỉ là `hint` hiển thị, không có handler (`composer.tsx:239`) |
| Textarea | `aria-label="Hỏi VisgniteAI"` `composer.tsx:156`; auto-resize tới `MAX_FIELD_HEIGHT_PX = 150` `composer.tsx:57,80-87`; **không bị disable** khi Turn chạy (chỉ nút đổi) |
| Draft | giữ ở shell state (`state.draft`), không local — `composer.tsx:75`, `shell-state.tsx:101` |

---

## 5. Sidebar / history

- Component: `Sidebar` `sidebar.tsx:38` → `Conversations` `sidebar.tsx:171` → `ThreadRow`
  `sidebar.tsx:228`.
- Data: `useThreads(true)` `sidebar.tsx:172` (`hooks/use-threads.ts:53`, TanStack Query,
  `queryKeys.threads`). TopBar và CommandPalette dùng cùng hook (`top-bar.tsx:23`,
  `overlays.tsx:122`).
- Mỗi row hiển thị: **một dot/pin icon + title truncate**, hết. `sidebar.tsx:301-313`.
  Không timestamp, không snippet, không message count. Title lấy qua `threadTitle`
  `sidebar.tsx:454-467` — fallback `Hội thoại DD/MM HH:mm` (Intl vi-VN, Asia/Ho_Chi_Minh).
  Row active: `aria-current="true"` + `bg-foreground/[0.06]` `sidebar.tsx:289,296-298`.
- **Không group theo thời gian** (không có Hôm nay / 7 ngày qua). Chỉ hai nhóm:
  - `Đã ghim` `sidebar.tsx:189` — chứa `NavRow "Danh mục theo dõi"` **disabled**
    (`sidebar.tsx:191-193`) + các thread `pinned_at !== null` (`sidebar.tsx:177`).
  - `Hội thoại` `sidebar.tsx:199` — phần còn lại; empty/loading dùng `QuietLine`
    (`sidebar.tsx:200-205`).
- Item disabled trong sidebar: `Bộ lọc cổ phiếu`, `Báo cáo đã lưu` (`sidebar.tsx:101-106`),
  `Danh mục theo dõi` (`sidebar.tsx:191`). `NavRow` disabled có badge "Sắp ra mắt" +
  `title="Sắp có"` (`sidebar.tsx:127,138-142`).
- Menu mỗi row (`ThreadMenu` `sidebar.tsx:367`): Ghim/Bỏ ghim · Đổi tên · Mở ở tab mới
  (`<a href="/?thread=…" target="_blank">` `sidebar.tsx:399`) · Xoá (destructive).
- Rename in place: `RenameField` `sidebar.tsx:420` — Enter/blur commit, Escape huỷ
  (`sidebar.tsx:437-445`).
- TopBar menu hội thoại (`top-bar.tsx:67-87`): Ghim · Đổi tên · Xuất PDF · Xoá — **cả 4
  disabled**, dù sidebar đã làm được ghim/đổi tên/xoá thật. Bất đối xứng đáng chú ý.

---

## 6. Share

- Dialog: `ShareDialog` `shell/overlays.tsx:203-268`, mở qua `dispatch({type:"overlay",
  overlay:"share"})` từ nút "Chia sẻ" `top-bar.tsx:91-97` và từ action share dưới câu trả lời
  (`view-chat.tsx:366`).
- **Không gọi endpoint nào.** Chỉ local state `scope: "private" | "team"` `overlays.tsx:205`;
  nút "Tạo liên kết chia sẻ · Sắp ra mắt" `disabled` `overlays.tsx:256-263`.
- Thông báo: `<UnavailableNote>` `overlays.tsx:250-252`, text
  `"Chưa tạo được liên kết — API chưa có endpoint chia sẻ hội thoại."`.
  Component `UnavailableNote` ở `primitives.tsx:301-310` (`role="status"`, tiêu đề
  "Tính năng sắp ra mắt").
- `ScopeRow` `overlays.tsx:270-298` dùng `role="radio" aria-checked` nhưng **thiếu
  `role="radiogroup"` bao ngoài** (`overlays.tsx:231`) — a11y gap.

---

## 7. Delete thread

Luồng: `ThreadRow` → `ThreadMenu.onDelete` `sidebar.tsx:344-353` → `useDeleteThread()`
`sidebar.tsx:244` (`hooks/use-threads.ts:135-146`) → `deleteThread(threadId)`
(`lib/alpha-desk/api.ts:79-81`, `DELETE /threads/{id}`).

- **Không có confirm dialog.** Chủ ý, ghi trong docstring `sidebar.tsx:360-366`: "Delete takes
  effect on the press… a second confirmation there was ceremony".
- **Không có undo**, không toast. `onSuccess` chỉ `desk.newThread()` nếu thread đang mở
  (`sidebar.tsx:349-351`).
- Cache: optimistic remove khỏi list + `removeQueries` cho thread detail
  (`use-threads.ts:141-146`). Không thấy `onError` rollback ở hook này.
- Đường thứ hai (TopBar → Xoá) **disabled** `top-bar.tsx:83-85`.

---

## 8. Copy

Ba chỗ, ba cách xử lý lỗi — đều **im lặng**:

| Chỗ | path:line | Xử lý lỗi |
|---|---|---|
| Copy câu trả lời (assistant) | `view-chat.tsx:28-30` `copyText()` → truyền vào `onCopy` `view-chat.tsx:365`; button ở `MessageActions` `alpha/message/message-actions.tsx:64-67` | `navigator.clipboard?.writeText(text).catch(() => {})` — swallow; nhãn "Đã chép" **optimistic**, đổi kể cả khi fail (`message-actions.tsx:53-67`, timer 1600ms) |
| Copy câu hỏi (user bubble) | `view-chat.tsx:506-515` | `try/await/catch {}` — `setCopied(true)` chỉ khi thành công (đúng hơn); reset sau 1600ms `view-chat.tsx:500-504` |
| Agentation devtool | `components/dev/agentation-toolbar.tsx:21` | ngoài scope UI sản phẩm |

Không có announce cho screen reader khi copy xong (chỉ đổi `aria-label`/`title` của
`IconButton`, `view-chat.tsx:535`).

---

## 9. Scroll

`view-chat.tsx` là toàn bộ logic scroll. Container riêng `overflow-y-auto overscroll-contain`
`view-chat.tsx:321-328` (page không scroll — `app-shell.tsx:36` `h-dvh overflow-hidden`).

| Hành vi | Có? | path:line |
|---|---|---|
| Auto-scroll theo nội dung mới | Có, khi `following` | `view-chat.tsx:255-279`, ngưỡng `FOLLOW_THRESHOLD_PX = 120` `:50`, tính trong `onScroll` `:281-289` |
| Pin câu hỏi mới lên **đỉnh** viewport (không phải đáy) | Có | `view-chat.tsx:189-250`; arithmetic ở `lib/alpha-desk/pin-question.ts::pinStep`; spacer `tail` `:409`; `ANCHOR_PAD_PX = 14` `:53` |
| Mở lại thread → nhảy xuống cuối | Có | `view-chat.tsx:198-207` |
| Reader wheel/touch huỷ pin | Có | `onWheel`/`onTouchMove` → `onUserScroll` `view-chat.tsx:292-295, 324-325` |
| Tôn trọng `prefers-reduced-motion` | Có | `scrollTo()` `view-chat.tsx:459-466` |
| **Nút "scroll to latest" / jump-to-bottom** | **Không có** | grep `scroll-to\|scrollToBottom\|xuống cuối` không hit trong `components/` |
| **New-content indicator** khi đang đọc lên trên | **Không có** | — |

Đây là gap UX rõ nhất: reader cuộn lên giữa lúc câu trả lời stream sẽ mất auto-follow
(`following.current = false`) và **không có affordance nào để quay lại đáy** ngoài cuộn tay.

---

## 10. Message surface

| Thành phần | File | Wire |
|---|---|---|
| Transcript list | `view-chat.tsx:329-402` | map `desk.entries` (`buildTranscript` ở `lib/alpha-desk/transcript`, gọi từ `desk-state.tsx:229-240`); 3 nhánh `user` / `assistant` / còn lại → `DraftMessage`; `kind === "analysis"` → `null` `view-chat.tsx:390` |
| Answer đã commit | `alpha/message/assistant-message.tsx:39` | props từ `view-chat.tsx:354-382` |
| Answer đang stream | `alpha/message/draft-message.tsx:34` | reveal pacer `hooks/use-answer-reveal.ts` gọi ở `desk-state.tsx:227` |
| Reasoning status | `alpha/message/reasoning-timeline.tsx` (622 dòng) | mở sẵn khi `running`, gập khi xong (`reasoning-timeline.tsx:20-31`); nhóm tool call theo `round` |
| Turn status (cancel/deadline/fail) + Retry | `alpha/message/turn-status.tsx` | `DraftMessage` `draft-message.tsx:77-81`; retry → `desk.retry` `view-chat.tsx:394` → `desk-state.tsx:269-275` (`retry_of_turn_id`) |
| Resend / regenerate | `view-chat.tsx:371-374` + `desk-state.tsx:291-298` `resend()` | `resendPlan` chọn retry vs submit mới |
| Refusal | `view-chat.tsx:423-439` `role="alert"` trên composer | `desk.refusal` = `turn.refusal?.message ?? threadError` `desk-state.tsx:348` |
| Actions dưới answer (5 nút) | `alpha/message/message-actions.tsx:69-...` | Hữu ích · Chưa đúng · Copy · Share · Regenerate |
| Flag 4 lý do | `alpha/message/flag-action.tsx` | mở từ thumbs-down `assistant-message.tsx:135-139` |
| Follow-ups | `alpha/message/follow-ups.tsx:13` | `onFollowUp={desk.submit}` `view-chat.tsx:376` |
| Sources tab | `shell/sources-tab.tsx:43` | `onOpenSources` → `open-sources` action `view-chat.tsx:377-379`; panel đọc lại transcript theo `state.sourcesMessageId` `sources-tab.tsx:48-51` |
| Canvas card trong transcript | `alpha/message/canvas-card.tsx:21` | `onOpenCanvas` → `open-canvas` `view-chat.tsx:380-382, 396-398` |
| Canvas panel | `canvas/canvas-panel.tsx:41` | `next/dynamic ssr:false` `inspector.tsx:35-46`; auto-open qua `canvas.ready` (`hooks/use-live-turn.ts:45`) → `desk-state.tsx:214-219` → reducer `canvas-ready` `shell-state.tsx:233-239`, tôn trọng `inspectorPinned` |
| Widget fallback | `canvas/widget-registry.ts:119-120` | version/kind lạ → `DataTableWidget`, `degraded: true` |

---

## 11. Design tokens

Hai file: `apps/web/tailwind.config.js` (CommonJS, **không** phải `.ts`) và
`apps/web/src/app/globals.css`.

**Palette là slate/near-black + amber — không có slate/amber của Tailwind mặc định.**
Toàn bộ là CSS var HSL trong `globals.css`:

| Nhóm | Token | Giá trị dark (`:root`) | path:line |
|---|---|---|---|
| Surface (6 bậc) | `--surface-ground` #101112 · `-panel` #17181a · `-raised` #1c1d1f · `-sunken` #202123 · `-menu` #232426 · `-bubble` #26282a | `210 6% 7%` → `210 5% 16%` | `globals.css:45-50` |
| Ink (7 bậc) | `--ink-display`, `--ink-1..6` (#fdfdfd → #8c8f93) | `0 0% 99%` → `214 3% 56%` | `globals.css:58-63` |
| Brand | `--primary` amber #f59331 = `30 91% 58%`; `--primary-foreground` = ground (ink-on-amber) | | `globals.css:73-74` |
| Market | `--positive` #3fbf6a `140 50% 50%` · `--negative` #e2574f `3 72% 60%` | | `globals.css:107-108` |
| Board VN | `--ceiling` #b18cf0 · `--reference` #e8c454 · `--floor` #5fc9d6 · `--caution` | | `globals.css:112-115` |
| Chrome | `--border` `220 4% 16%` · `--hairline` `220 4% 14%` · `--ring` = amber · `--radius` `0.625rem` | | `globals.css:87-91` |
| Charts | `--chart-1..5` = amber, đỏ, violet, vàng, cyan | | `globals.css:124-128` |
| Light theme | class `.light` ghi lại toàn bộ; amber tối xuống `30 76% 36%` (#a25c16) để carry text | | `globals.css:135-181` |

Tailwind map: `colors.surface.*`, `colors.ink.1..6` + `ink.display`
(`tailwind.config.js:92-115`), `positive/negative/hairline/interactive/nav/ceiling/reference/
floor/caution` (`:117-131`).

**Typography** — 3 face qua `next/font/google` ở `app/layout.tsx`:
- `Inter` subsets `["latin","vietnamese"]` → `--font-inter` (`layout.tsx:20-24`)
- `JetBrains_Mono` → `--font-jetbrains-mono` (`layout.tsx:27-31`)
- **`Newsreader`** axes `["opsz"]` → `--font-newsreader` (`layout.tsx:44-49`); stack
  `serif: ['var(--font-newsreader)','Georgia','Times New Roman','serif']`
  `tailwind.config.js:25`. Dùng **duy nhất** cho greeting (`view-chat.tsx:110` `font-serif`).

Scale chữ tự đặt, base 15px (`globals.css:198`): `eyebrow 0.7rem` · `micro 0.74rem` ·
`meta 0.8rem` · `control 0.86rem` · `row 0.9rem` — `tailwind.config.js:39-47`.
Radius: `card 14px`, `composer 18px`, `pill 99px` (`:79-81`). Shadow: `menu/composer/panel/
modal` (`:83-89`). Motion: `duration-panel 340ms` + `ease-panel/ease-sidebar`
cubic-bezier(0.22,1,0.28,1) (`:63-71`). `gridTemplateColumns.fit = minmax(0,1fr)` (`:36`).

Animation `animate-vg-*` khai ở `globals.css:239-299` (keyframes `vg-fade-in`/`vg-message-in`/
`vg-row-in`/`vg-bar-grow`, utility class `:284-299`, có block `prefers-reduced-motion` `:312`),
không ở tailwind config `extend.animation` — dùng ở `top-bar.tsx:45`, `primitives.tsx:118`, `view-chat.tsx:524`.

---

## 12. A11y hiện có

**aria-label tiếng Anh còn sót (5 chỗ):**

| path:line | Nhãn |
|---|---|
| `alpha/message/message-shell.tsx:29` | `aria-label="Assistant message"` |
| `shell/inspector.tsx:68` | `aria-label="Chat inspector"` |
| `shell/inspector.tsx:79` | `aria-label="Resize inspector panel"` |
| `shell/inspector.tsx:100` | `aria-label="Inspector"` (tablist) |
| `shell/inspector.tsx:120` | `label="Close inspector"` (IconButton) |

Còn lại đều tiếng Việt (`sidebar.tsx:60,65`, `top-bar.tsx:43,54`, `composer.tsx:156,169`,
`view-chat.tsx:431,535,539,546`, widget canvas `canvas/widgets/*`).

**Focus ring:** `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`
trên `IconButton` `primitives.tsx:94`, `MenuItem` `primitives.tsx:153`, `NavRow`
`sidebar.tsx:130`, `RenameField` `sidebar.tsx:448`. **Thiếu** trên: nút Chia sẻ
`top-bar.tsx:94`, nút Send `composer.tsx:214`, nút Dừng `composer.tsx:191`, ThreadRow button
`sidebar.tsx:294-299`, tab inspector `inspector.tsx:108`, palette row `overlays.tsx:173`,
`ScopeRow` `overlays.tsx:289`, `FollowUps` button `follow-ups.tsx:31`, `CanvasCard`
`canvas-card.tsx:36`.

**Touch target icon button:** `primitives.tsx:96` — `size === "sm" ? "size-7" : "size-[30px]"`
→ **28px và 30px**. Cả hai **dưới mức 44×44 của WCAG 2.5.5 / 24×24 của 2.5.8-AAA-minimum**.
Nút Send lớn hơn: `size-[34px]` `composer.tsx:214`. Handle resize inspector `w-1` = **4px**
(`inspector.tsx:96`) nhưng có keyboard fallback (`inspector.tsx:84-95`, ArrowLeft/Right/Home/
End + `role="separator"` với `aria-valuemin/max/now`).

**Có sẵn:** focus trap + restore focus trong `Scrim` (`overlays.tsx:50-73`,
`focusableElements` `:98-109`); `role="dialog" aria-modal="true"` `:78-80`; `role="tablist"/
"tab" aria-selected` `inspector.tsx:100-106`; `role="alert"` cho refusal `view-chat.tsx:425`;
`role="status"` cho turn status / UnavailableNote; `aria-current` cho thread active
`sidebar.tsx:289`; `aria-expanded`/`aria-haspopup` trên mọi trigger menu; `aria-hidden` cho
spacer `view-chat.tsx:409` và sidebar khi đóng `sidebar.tsx:49`; chart có `role="img"` +
aria-label tiếng Việt.

**Gap:** không có skip link; `aria-hidden={!open}` trên sidebar nhưng **các button bên trong
vẫn focusable** (không có `inert`/`tabIndex={-1}`) — `sidebar.tsx:49`; `ScopeRow` radio thiếu
`radiogroup`; row action reveal bằng `opacity-0` + `focus-within` (`view-chat.tsx:534`,
`sidebar.tsx:326`) là đúng cách; không thấy `aria-live` cho answer đang stream.

---

## 13. Test hiện có

`components/shell/`: 4 file, **55 case**.

| File | Case |
|---|---|
| `shell/shell.test.tsx` | 34 |
| `shell/thread-menu.test.tsx` | 10 |
| `shell/sources-tab.test.tsx` | 8 |
| `shell/view-chat-pin.test.tsx` | 3 |

Toàn web (grep tĩnh, **không chạy** `pnpm test`): **37 file test, 446 `it()`/`test()`**
(`rg -c '^\s*(it|test)\(' src --glob '*.test.*'`). Con số 406 trong `CLAUDE.md` là mốc
Phase 0 (2026-08-25); đã tăng thêm cùng canvas + widget mới.

---

## 14. Dev tooling trong UI

| Thứ | File | Gate |
|---|---|---|
| **Agentation** (devtool annotate UI cho AI agent) | `components/dev/agentation-toolbar.tsx:19-22`, mount `app/layout.tsx:105` | `if (process.env.NODE_ENV === "production") return null` `agentation-toolbar.tsx:20`; package nạp qua `dynamic(..., {ssr:false})` `:14-17` |
| **canvas fixture** — nút pill góc **dưới-trái** | `components/dev/canvas-fixture.tsx:36-60` (`fixed bottom-3 left-3 z-50`, label `"canvas fixture"` `:59`); wrapper `canvas-fixture-toolbar.tsx:20-23`, mount `app/layout.tsx:106-109` | gate **hai lần** `NODE_ENV`: `canvas-fixture-toolbar.tsx:21` và `canvas-fixture.tsx:37`; JSON fixture (`contracts/fixtures/artifact-intraday-liquidity.json`, `canvas-fixture.tsx:26`) chỉ nạp qua dynamic import nên không vào production bundle |

Panel fixture mở ra drawer `w-[420px]` bên phải (`canvas-fixture.tsx:53`), có sẵn 2 block
`DEGRADED` cố tình sai version/kind (`canvas-fixture.tsx:44-47`) để nhìn thấy đường fallback
`data_table`.

Không có biến `NEXT_PUBLIC_*` nào gate hai toolbar này — chỉ `NODE_ENV`. Các
`NEXT_PUBLIC_API_URL`/`INTERNAL_API_URL`/`APP_ORIGIN` chỉ dùng cho transport
(`lib/api.ts:11-14`, `app/api/alpha-desk/[...path]/route.ts:100`).

---

## Quan sát đáng đưa vào plan UX

1. **Không có jump-to-bottom / new-content indicator** (§9) — reader cuộn lên giữa stream bị
   kẹt, không affordance quay lại.
2. **Empty state trống trơn** (§3) — chỉ greeting + composer, không gợi ý câu hỏi nào, dù
   `FollowUps` đã có sẵn component để tái dùng.
3. **Greeting tiếng Anh trong sản phẩm tiếng Việt** (§3) — 18 dòng hardcode, docstring còn
   trỏ tới file đã xoá `shell/view-new`.
4. **Bất đối xứng TopBar vs Sidebar** (§5) — cùng 4 hành động thread, sidebar làm được thật,
   TopBar disabled hết.
5. **Touch target 28–30px** dưới ngưỡng WCAG (§12), và ~9 control thiếu focus ring.
6. **Sidebar đóng ở <768px không tự mở lại** khi nới rộng (`shell-state.tsx:288-290`), và
   button bên trong vẫn focusable khi `aria-hidden` (§12).
7. **Xoá thread không confirm, không undo** (§7) — chủ ý theo docstring, nhưng không có
   toast/rollback nào nếu request fail.
8. **18 control disabled** rải khắp (7 attach menu + 4 TopBar menu + 3 sidebar nav + 4 account
   menu + 1 nút Share)
   đều gắn badge "Sắp ra mắt" — mật độ cao, đáng cân lại trong plan.
