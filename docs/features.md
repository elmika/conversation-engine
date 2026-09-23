# Feature Overview — Conversation Engine

This document lists all user-facing features of the Conversation Engine application.
Intended as a reference for UX review.

---

## 1. Identity & Setup

### 1.1 UUID-in-URL identity
There is no sign-in or account. Each learner is identified by an opaque UUID that lives in the URL: every page is served under `/u/{userId}/…`. On first visit the root page mints a UUID, stores it in `localStorage`, and redirects to that learner's personal space. Returning without a URL (or via a legacy link) re-resolves the same UUID from `localStorage`.

Legacy bare routes (`/chat`, `/history`) and a bare `/u/{userId}` (no `/chat` or `/history` suffix) each redirect straight to their user-scoped equivalent — `/history` never passes through `/chat` on the way there, so simply loading or bookmarking one of these URLs can never silently start a new course session as a side effect. The top nav's Chat/History links are always built from the current UUID (from the URL if already present, otherwise from `localStorage`) for the same reason.

Every `/u/{userId}/…` page is gated behind an identity check before it renders. A UUID matching what's already stored (the common case), or the first-ever visit under this browser with nothing stored yet, is trusted immediately — no check needed. A UUID naming a *different* id than the one already stored (e.g. following a direct link to another learner's session) is only trusted once confirmed to be a known learner (has a profile, or at least one conversation); once trusted, it's adopted as the browser's current identity in `localStorage`, overwriting whatever was stored before. This matters whenever something redirects through the root page (e.g. the consent gate) — without adopting first, that redirect would resolve against the old stored UUID instead of the one actually being viewed.

A mistyped or otherwise unrecognized UUID is never adopted and never renders the page underneath — instead it shows a "We couldn't find that session" screen with a **Go to my session** link back to the learner's own space. `localStorage` is left completely untouched in this case, so a typo can't silently orphan the browser from its real session or spin up a phantom learner under a bogus id.

### 1.2 Personal space & bookmarking
All of a learner's conversations, history, and profile are scoped to their UUID. Bookmarking the `/u/{userId}/…` URL is how a learner returns to their session on the same browser. A conversation is only visible to the UUID that created it — requests under a different UUID are treated as non-existent (not enumerable across users).

### 1.3 Setup flow (new learner)
A learner with no profile is routed into a guided **setup conversation** instead of a normal chat. This conversation (the `user-profile-collection` assistant) collects the learner's background and goal and proposes a course outline. The framing Q&A asks name, work, "what would you like to learn with me", and session length, one per turn, in that order — the opening message itself is the name question, so the assistant never re-asks a question the learner has already answered.

If a learner's reply to the framing question that would otherwise complete the Q&A is itself a clarifying question rather than an answer (e.g. "what skill are you referring to?"), the flow stays in the framing phase for one more turn instead of jumping straight to the outline off an unanswered question — checked synchronously on that exact turn, since it's too late to correct on any later turn.

Once an outline is proposed, the assistant asks the learner to confirm it looks right or say what to change, rather than prompting them to click "Let's start" — the outline can be refined any number of times (each refinement re-asks for confirmation), and moving on to the course is always the learner's own action via the button (§1.5), never something the assistant announces or ushers them toward.

### 1.4 AI opens first
Per the design principle *"the AI always opens — no blank input ever"*, the assistant sends the first message automatically when a fresh chat is opened, for both audiences:
- **New learners** — the setup conversation opens with the profile-collection prompt.
- **Profiled learners** — navigating to a fresh chat auto-opens a new course session (an AI recap/opening message) for the currently selected course.

While the learner's profile status is still loading, the input is briefly disabled so a conversation is never created with the wrong prompt.

### 1.5 Complete setup ("Let's start")
During a setup conversation, once the outline has been proposed, a **Let's start** button (sparkle icon) appears in the header. Clicking it:
1. Runs profile + course-outline extraction against the setup conversation and writes the learner's profile and course section files.
2. Marks the setup conversation as ended.
3. Immediately opens the first real course session (AI-initiated).

Extraction and file writes happen **before** the conversation is ended, so if extraction fails the setup conversation stays active and the learner can retry — nothing is left half-finished. While the request is in flight the button shows a spinner and is disabled. The button is hidden for the entire framing Q&A (the 4 opening questions) and appears only once the outline exists; the backend independently rejects a complete-setup call made before then (400), so a request racing ahead of the UI can't silently extract a course/profile from a partial transcript.

### 1.6 Per-user isolation
Conversation listing, messages, rename, delete, end-session, summary, and setup are all scoped to the learner's UUID. Reading or modifying another learner's conversation returns *not found* (404) or is a silent no-op (idempotent 204 on delete), so resources are never enumerable across learners.

### 1.7 Consent gate
Between minting/resolving the UUID (§1.1) and the redirect into chat, the root page checks whether this UUID has a recorded consent record. A fresh UUID has never consented, so a disclosure screen is shown instead of redirecting: what data is collected (name, role, goal, full session transcripts), who can see it, that messages go to OpenAI, the pilot's as-is/no-guarantee status and expected ~2-week duration, and how to request deletion. A checkbox ("I understand and agree to this") gates a **Continue** button, disabled until checked. Consent is recorded server-side, timestamped and keyed to the UUID — not a `localStorage`-only flag, so it's provable later, not just a client-side gate that vanishes if storage is cleared. A returning UUID with a recorded consent skips the screen entirely and redirects straight to chat as before. Conversation-creation endpoints independently reject any UUID with no recorded consent (403), as defense in depth against the frontend gate being bypassed (e.g. a direct API call). This 403 is also the recovery path for a learner who never saw the gate at all — e.g. a browser tab left open on `/chat` from before this feature shipped, or any deep link straight into chat that skips the root page: the first conversation-creation attempt hits the 403, and the client automatically redirects to `/`, which re-checks consent status and shows the screen. Completing it redirects straight back into chat, so the learner isn't left at a dead end with no way to proceed.

### 1.8 Force a fresh identity (`/new`)
`/new` always mints a brand-new UUID and stores it, discarding whatever was there before — unlike the root page, which reuses an existing stored UUID if one exists. For testing/demos where a fresh learner is needed without manually clearing browser storage. Since consent is always unrecorded for a freshly-minted id, it shows the consent screen directly (skipping the consent-status check the root page does) and, once consented, goes straight to `/u/{id}/chat`. Because the id is already correctly stored before that redirect, it's trusted immediately by the identity check in §1.1 — never at risk of landing on the "not found" screen.

---

## 2. Chat

### 2.1 Send a message
The core interaction. The user types a message and receives a streaming response from the AI assistant. Responses render as formatted markdown (headings, lists, tables, code blocks).

### 2.2 Streaming responses
The assistant's reply appears word-by-word in real time. A typing indicator is shown while the response is loading. The view auto-follows the streamed text, but the reader stays in control: scrolling up at any point (wheel, trackpad, touch, or keyboard) immediately stops the auto-follow so you can read earlier text while the response keeps streaming. Scrolling back to the bottom re-engages auto-follow.

The course-outline-compile step during setup (§1.3) runs on a slower, higher-quality model and can take up to ~2 minutes — during that wait it shows a dedicated loading state ("Compiling your personalised course… This can take a minute or two.") with a live elapsed-seconds counter, instead of the generic typing indicator, so the wait reads as "still working" rather than "frozen."

### 2.3 Stop / cancel streaming
A **Stop** button replaces the input field while the assistant is responding. Clicking it immediately halts the stream.

### 2.4 Send key preference
A toggle in the chat header bar switches between two send modes:
- **Enter to send** (default) — `Enter` sends the message, `Shift+Enter` inserts a new line
- **Ctrl+Enter to send** — `Enter` inserts a new line, `Ctrl+Enter` (or `Cmd+Enter`) sends

The active mode is shown as a labelled button in the header and as a persistent hint line below the input field. The preference is saved to `localStorage` and persists across sessions.

### 2.5 Code syntax highlighting
Code blocks in assistant responses are syntax-highlighted. Supported languages: TypeScript, JavaScript, TSX/JSX, Python, Bash, JSON, SQL, YAML, CSS, PHP, Java, Rust, Go.

### 2.6 Copy code block
Each code block has a **Copy** button that copies just the code snippet to the clipboard.

### 2.7 Copy full message
Each assistant message has a **Copy** button (visible on hover) that copies the entire message content.

### 2.8 Edit and resend (message rewind)
Any past user message can be edited and resent. Hovering over a user message reveals a **pencil icon**. Clicking it opens an inline editor pre-filled with the original message. The user can modify the text and click **Resend** (or `Ctrl+Enter`). This truncates the conversation from that point onward and streams a new response — effectively branching the conversation from the edited message.

### 2.9 ~~Response timings~~ (removed)
Previously: after each complete response, a small badge showed TTFB and total response time. Removed — this leaked platform-internal detail (model name, latency) to the learner-facing UI/API response. The data is still recorded server-side (the `runs` table) for every turn; it's just no longer returned to or rendered for the learner. Section number kept stable (not renumbered) since `.notes/product-design.md` cross-references §2.10–§2.12 below.

### 2.10 Course session pacing (open → teach → wind down)
A course session moves through three moments automatically, driven by the platform (not the model guessing):
- **Opening** — the AI's first message presents the module list and where to pick up, and confirms the learner's usual session length, offering to adjust it for today.
- **Teaching** — short, question-led exchanges: the tutor reacts to what the learner said, adds one thing, and hands back with exactly one question, rather than lecturing. How long the tutor waits before it may judge a module "done" (see 2.10) scales with the learner's planned session length, so a 30-minute session isn't held to the same turn count as a 10-minute one.
- **Wind-down** — the AI shifts to wrapping up once **either** the session's time is up **or** the current module's objective has been met: it summarises what was covered, names what's next, and invites the learner to **End Session** (it won't start new material).

### 2.11 Adjustable session length
Each learner has a default session length (from their profile). In the opening message the AI offers to adapt it for the current session; if the learner asks for more or less time in chat ("let's do 30 today"), that length is captured and used to time the wind-down for this session. Unclear or implausible values are ignored, leaving the default in place.

### 2.12 Continue past wind-down
Wind-down is a suggestion, not a cutoff. If the learner's reply during wind-down clearly asks to keep learning ("actually can we keep going?"), the tutor acknowledges warmly and the *next* turn continues teaching normally — the session gets more time automatically, and it's no longer treated as having met the module's objective. Agreeing to stop, or asking one quick clarifying question, keeps the session in wind-down (answered briefly, then wrapping up as before). Ending the session is still always a deliberate action — the **End Session** button.

---

## 3. Conversations

### 3.1 New conversation
A **New conversation** button (pencil icon in the top bar, or `+` in the sidebar) starts a fresh chat. For a profiled learner this immediately opens a new AI-initiated course session for the selected course. The button is **disabled while a conversation is active** — only one active (non-ended) conversation is allowed at a time, so the current session must be ended first (the button tooltip explains this).

### 3.2 Auto-naming
Conversations are automatically named after the first user message (truncated to 60 characters), or — for AI-opened course sessions — after the course title. The name appears in the sidebar and history table.

### 3.3 Rename conversation
Conversations can be renamed inline. In the sidebar, clicking the pencil icon next to a conversation name opens an inline text field. In the history table, the same pencil icon is always visible. Pressing `Enter` commits, `Escape` cancels.

### 3.4 Delete conversation
Any conversation can be deleted. A confirmation modal prevents accidental deletion. Deleting removes the conversation and all its messages permanently.

### 3.5 Resume conversation
Clicking a conversation in the sidebar or history table reopens it with its full message history.

### 3.6 End Session
An **End Session** button (exit icon) in the chat header bar is shown when an active (non-setup) conversation is open and the stream is not running. Clicking it:
1. Sends `POST /u/{userId}/conversations/{id}/end-session` to the backend.
2. While the request is in flight, the button shows a spinner and is disabled.
3. The backend marks the conversation ended immediately and returns; progress synthesis (an LLM wrap-up that updates the learner's `sections/progress/{userId}.md` snapshot) runs as a background task so the learner is never blocked.
4. A **session summary card** replaces the input, showing the course name, modules covered, and the suggested next step, with a **Start new session** action. The card can be dismissed to a compact "Session ended" banner (with a **View summary** link to reopen it). Module titles render as formatted Markdown (matching the rest of the chat), and each module is prefixed with a status marker — ✓ for done, → for the module in progress, a plain number for upcoming — derived from the learner's progress record, matching the markers already used in the in-chat module list.

Attempting to start a new conversation while one is active returns 409.

### 3.7 Download conversation
A **Download** button (download icon) in the chat header is shown whenever the open conversation has at least one message and the stream is not running. It saves the full conversation client-side as a single Markdown file (`conversation-<course>-<id>-<date>.md`) — no server round-trip. The file is designed to be read by both a human and a machine: a YAML frontmatter block carries metadata (conversation id, course prompt, created/ended/exported timestamps, message count), followed by the transcript with one heading per turn (**Tutor** / **Learner**, with timestamps). If the session has been wrapped, the **session summary** (course, modules covered, where to pick up next time) is appended at the end.

### 3.8 Active / ended conversation state
Conversations have an `ended_at` timestamp (null when active). In the sidebar and history table:
- **Active conversations** show a green **Active** badge.
- Ended conversations show no badge (most conversations are ended).

---

## 4. Conversation History

### 4.1 History table
A dedicated `/u/{userId}/history` page lists the learner's conversations in a paginated table with the following columns:
- **Name** — the conversation name (or a truncated ID if unnamed), linking to the conversation
- **First message** — a preview of the opening user message
- **Created** — creation date
- **Last activity** — date of the most recent message

### 4.2 Pagination
The history table paginates at 20 conversations per page, with numbered page buttons and previous/next arrows.

### 4.3 Inline rename from history
The pencil icon in the history table allows renaming directly without navigating to the conversation.

### 4.4 Delete from history
The trash icon in the history table opens a confirmation modal and deletes the conversation.

### 4.5 Mobile history layout
Below the `md` breakpoint (768px), the five-column table (§4.1) doesn't fit a phone's width without clipping. Instead, `/u/{userId}/history` renders a stacked card list — the same compact row component used by the sidebar's conversation list (§5.1) — showing name, an "Active" badge for unfinished sessions, and inline rename/delete, with pagination (§4.2) unchanged. The "First message" preview column is dropped in this view for space. On this card list, the rename/delete icon buttons use a 36×36px touch target (matching the app's standard icon-button size) rather than the sidebar's compact hover-revealed icons, since this is a touch-first surface with no hover state.

---

## 5. Sidebar

### 5.1 Conversation list
A collapsible sidebar lists recent conversations, ordered by most recently created. Clicking a conversation navigates to it. Visible on tablet/desktop widths (`md` breakpoint, 768px) and above only — see §5.4.

### 5.2 Toggle sidebar
A **panel icon** in the top bar shows or hides the sidebar. Desktop/tablet only (see §5.4); the icon is hidden on mobile since there is nothing to toggle there.

### 5.3 Active conversation highlight
The currently open conversation is highlighted in the sidebar.

### 5.4 Mobile navigation
Below the `md` breakpoint (768px), the inline sidebar is replaced by a fixed bottom tab bar (Chat / History / Admin, mirroring the top nav's tabs) so a narrow phone screen isn't dominated by a 256px-wide panel. The **History** tab routes to the existing `/u/{userId}/history` table (§4.1) as the mobile equivalent of the sidebar's conversation list — the sidebar's own "New conversation" button is not needed there, since the top bar's pencil-icon "New conversation" button (§3.1) already provides that entry point on both mobile and desktop. Each bottom-nav item marks itself `aria-current="page"` when active.

---

## 6. Assistants (Prompts)

### 6.1 Multiple assistants
The application supports multiple AI personas, each with a distinct system prompt. Assistants are defined as Markdown files in a `prompts/` directory and stored in the database on startup.

### 6.2 Which assistant drives a conversation (code-owned, not learner-chosen)
Removed 2026-09-17: the chat header used to show a prompt/course dropdown (open before a conversation started, locked to a read-only label once active). It's gone — which prompt opens a conversation is now derived entirely server-side from the learner's profile state (setup vs. their course), the same "code owns deterministic state, never client input" principle the lesson/setup phase orchestrators already follow. This also closed a real gap: the underlying request field the dropdown wrote to had no server-side authorization check, so any caller (not just the UI) could previously force an arbitrary prompt. Internal test/comparison tooling that legitimately needs to pick a specific prompt uses the admin-only `/admin/u/{userId}/...` routes instead (`docs/model-decisions.md`, `docs/prompts.md` "Model presets").

### 6.3 Persisted prompt library
Prompts are stored in the database and served via `GET /prompts`. New assistants can be added by dropping a `.md` file into the `prompts/` directory and restarting the service — no code changes required.

**Current assistants:**
- **Default Assistant** — general-purpose concise assistant
- **Conflict Coach** — helps reason calmly through workplace conflicts
- **TypeScript Mentor** — teaches TypeScript from first principles
- **Profile Collection** — guides a new learner through setup (profile + goal + proposed outline)
- **Course Session Init** — opens a course session with an AI-initiated recap

### 6.4 Per-prompt model preference
Each assistant can declare a preferred OpenAI model via a `model:` field in its `.md` frontmatter (e.g. `model: gpt-4o-mini`). When set, that model is used for all conversations with that assistant unless overridden per-request.

### 6.5 Active / disabled state
Prompts have an `is_active` flag. Disabled prompts are soft-deleted: they no longer appear in `GET /prompts`, but their data is preserved so existing conversation history remains intact. Disabled prompts can be re-enabled at any time. Prompts that have never been used in a conversation can be fully hard-deleted.

### 6.6 Template variables in system prompts
System prompts support template variables that are resolved at the moment each LLM call is made. Resolution happens in two passes: file section tags are expanded first, then time tags are resolved on the assembled text.

**Time tags (`{{namespace:tag}}` format):**
| Tag | Resolves to |
|---|---|
| `{{time:current}}` | Current UTC time at minute precision, e.g. `2026-03-26 21:42 UTC` |
| `{{time:conversation-start}}` | UTC time when the conversation was created (minute precision, consistent across all turns) |
| `{{time:lesson-time-spent}}` | Elapsed time since conversation start, e.g. `5 minutes 30 seconds` |

**File section tags (valueless, no colon):**
| Tag | Resolves to |
|---|---|
| `{{course}}` | Contents of `sections/course/{userId}.md` |
| `{{user}}` | Contents of `sections/user/{userId}.md` |
| `{{progress}}` | Contents of `sections/progress/{userId}.md` |

File section tags allow prompts to reference large, stable content blocks (course material, user profiles, session progress) stored per-learner in separate Markdown files. The files are written by the setup flow and progress synthesis, and read at render time — editing a section file takes effect immediately without restarting the service. The Admin preview (which has no learner context) falls back to the `default` user's files. Section files may themselves contain `{{time:*}}` tags, which are resolved in the second pass. A missing section file at render time produces a 400 error.

Templates are validated when a prompt is saved via the Admin panel. A prompt containing an invalid tag (malformed format, unknown namespace, or unknown tag name) is rejected with an error — bad templates cannot be persisted. File section tags are accepted at save time; file existence is not checked until render time.

### 6.7 Preview rendered prompt
A **Preview** button (scan icon) on each prompt card in the Admin panel opens a dialog showing the fully assembled and rendered system prompt — with all template variables (time tags and file section tags) resolved to their current values. The preview is read-only and can be scrolled for long prompts.

---

## 7. Model Selection

### 7.1 Model registry
A static registry of supported OpenAI models (`app/domain/model_registry.py`) is served via `GET /models`. Each entry has a `slug` (the OpenAI model ID), a human-readable `name`, and a `description`. The default model is `gpt-4.1`. Which model each task (each prompt) actually uses is tracked in `docs/model-decisions.md`, not reproduced here — that list changes as models are compared/switched and would drift out of sync with this file otherwise.

### 7.2 Which model answers a turn (code-owned, not learner-chosen)
Removed 2026-09-17: the chat header used to show a model dropdown (default "Default (auto)", model descriptions as tooltips) letting a learner pick any registered model for their messages. It's gone, for the same reason as the prompt selector (6.2) — and the same real gap: the request field it wrote to had no server-side authorization check, so any caller could pick an expensive model tier for every turn regardless of what the UI showed. Which model runs is now purely `prompt.model` (the assistant's declared preference, `docs/model-decisions.md`) falling back to the global default — never client input on the learner-facing routes. Internal comparison tooling that needs to override a model uses the admin-only routes (see 6.2).

### 7.3 Model badge
After each streaming response, the timings badge shows the model that was actually used (e.g., `gpt-5.4-mini · TTFB: 120ms · Total: 800ms`) — the resolved model from the backend (the prompt's declared preference, or the global default).

### 7.4 Per-request model override
API callers can pass `model_slug` in any conversation request body to override the model for that specific request. Resolution priority (highest → lowest):
1. `model_slug` in the request body
2. `model` field on the selected prompt
3. Global `settings.default_model` (default: `gpt-4.1`)

Passing an unknown `model_slug` returns a 400 error.

---

## 8. Admin

### 8.1 Admin panel
A dedicated `/admin` section provides full management of prompt personas.

### 8.1a Admin token gate
`/admin` and `/admin/conversations` share one gate (`app/admin/layout.tsx`) — a lightweight "paste your admin token once" prompt, no login system, just a single token input. The token is validated against the backend before access is granted (not merely stored), so a stale or wrong token never reveals admin content. The token is kept in `sessionStorage` only (cleared when the tab closes, not shared across browser restarts). A **Log out** button (top-right, next to the "Admin" heading) clears it. A 401 from any admin action (mutating a prompt, viewing usage or conversations) clears the stored token and re-prompts the gate. The mutating/sensitive prompt routes (`POST/PUT/PATCH/DELETE /prompts*`, `GET /prompts/{slug}/render`), `GET /admin/usage/today`, and `GET /admin/conversations*` all require this token server-side; `GET /prompts` (the learner-facing persona list) stays open — see `docs/roadmap.md` for the accepted residual gap this implies.

The main nav bar's **Admin** tab is hidden unless a token is currently present in the browser (cosmetic — the token gate itself is what actually enforces access, not the tab's visibility).

### 8.1b Admin conversation viewer
`/admin/conversations` lists every learner's conversations, paginated, newest first, with a **User** column identifying the owner (a short prefix of their opaque id). Read-only — no rename/delete, unlike a learner's own History page. Clicking a row expands its transcript in place (role-labeled messages, scrollable) for support/QA purposes, fetched on first expand. A "Prompts" / "Conversations" sub-nav under the Admin header switches between this and the prompt-admin panel (8.1).

### 8.2 Create prompt
A **New Prompt** button (top-right) opens a dialog with fields for slug, name, system prompt, and optional model override. The slug must be lowercase alphanumeric with hyphens/underscores. Duplicate slugs are rejected with an inline error.

### 8.3 Edit prompt
An **Edit** button (pencil icon) on each active prompt card opens the same dialog pre-filled. The slug is read-only when editing. Changes take effect immediately.

### 8.4 Disable / enable prompt
An **eye-off** button on each active card soft-deletes the prompt (sets `is_active=false`). Disabled cards are grayed out with a **Disabled** badge and show an **eye** button to re-enable. Disabled prompts no longer appear in `GET /prompts`.

### 8.5 Show disabled prompts
A **Show disabled** checkbox at the top of the admin panel toggles display of disabled prompt cards alongside active ones.

### 8.6 Render prompt preview
`GET /prompts/{slug}/render` returns the prompt's system prompt with all `{{namespace:tag}}` template variables resolved to their current values. An optional `?conversation_id=` query parameter anchors `{{time:conversation-start}}` and `{{time:lesson-time-spent}}` to a specific conversation's start time; without it, both resolve to the current time (a "new conversation" preview). Returns 404 if the slug or conversation ID is not found.

### 8.7 Delete prompt
A **trash** icon on each card opens a confirmation dialog to permanently delete the prompt. If the prompt has been used in any conversation, deletion is blocked with an error message (use Disable instead).

---

## 9. Usage Limits

### 9.1 Server-side $ spend ceilings
Before every LLM call, the backend checks estimated $ spend against three ceilings, checked
platform → user → session: platform-wide per day, per-user per day, and per session. Defaults
(tunable via env var, no code change): session $0.50, user/day $1.00, platform/day $5.00.

### 9.2 Friendly block message
When a ceiling is hit, the learner sees a plain-language message in place of the assistant's
reply instead of an error (e.g. "SkillForge has hit today's usage limit platform-wide — please
try again tomorrow."). For a non-streaming turn this appears as a normal assistant message; for
a streaming turn it arrives as the terminal SSE `done` event's `error` field. No real LLM call is
made when a cap is already exceeded.

### 9.3 Admin spend visibility
`GET /admin/usage/today` (admin token required — see 8.1a) returns today's platform-wide $
spend and a per-user breakdown, for a quick sanity-check during the pilot. Not a full cost
dashboard.

---

## Notes for UX Review

- **Rewind vs. edit history** — the rewind feature (§2.8) permanently deletes the tail of the conversation. There is no undo, and no way to view the "old" branch after rewinding. Consider whether users should be warned more explicitly, or whether soft-delete / branching history would be more forgiving.
- **Course is locked per conversation** — the assistant/course selector (§6.2) is fixed at conversation creation and shown as a read-only label thereafter. This removes the old mid-conversation switching ambiguity, but means a learner who picked the wrong course must end the session and start a new one. Consider how clearly the locked state communicates this.
- **Identity is device-bound** — the learner UUID (§1.1) lives in `localStorage` and the URL. Clearing browser storage or switching devices, without the bookmarked `/u/{userId}/…` URL, starts a brand-new learner with no history or profile. Consider surfacing/exporting the URL so learners don't silently lose their progress.
- **Setup is a one-way gate** — completing setup (§1.5) ends the setup conversation and writes the profile/course files. There is currently no in-product way to redo setup or edit the captured profile afterwards.
- **Conversation naming** — auto-names are generated from the first user message (or course title). If the first message is short or generic (e.g. "Hi"), the name won't be descriptive. Consider an option to regenerate the name, or to auto-name from an AI summary.
- **Stop button placement** — the Stop button currently replaces the entire input area during streaming. Consider whether it's better placed as an overlay or alongside the input to maintain visual continuity.
- **History vs. sidebar** — there are two entry points to past conversations (sidebar and `/history`). The sidebar is quick-access; the history page offers search-ready table layout. The relationship between the two is not currently explained to the user.
