# Feature Overview — Conversation Engine

This document lists all user-facing features of the Conversation Engine application.
Intended as a reference for UX review.

---

## 1. Chat

### 1.1 Send a message
The core interaction. The user types a message and receives a streaming response from the AI assistant. Responses render as formatted markdown (headings, lists, tables, code blocks).

### 1.2 Streaming responses
The assistant's reply appears word-by-word in real time. A typing indicator is shown while the response is loading.

### 1.3 Stop / cancel streaming
A **Stop** button replaces the input field while the assistant is responding. Clicking it immediately halts the stream.

### 1.4 Send key preference
A toggle in the chat header bar switches between two send modes:
- **Enter to send** (default) — `Enter` sends the message, `Shift+Enter` inserts a new line
- **Ctrl+Enter to send** — `Enter` inserts a new line, `Ctrl+Enter` (or `Cmd+Enter`) sends

The active mode is shown as a labelled button in the header and as a persistent hint line below the input field. The preference is saved to `localStorage` and persists across sessions.

### 1.5 Code syntax highlighting
Code blocks in assistant responses are syntax-highlighted. Supported languages: TypeScript, JavaScript, TSX/JSX, Python, Bash, JSON, SQL, YAML, CSS, PHP, Java, Rust, Go.

### 1.6 Copy code block
Each code block has a **Copy** button that copies just the code snippet to the clipboard.

### 1.7 Copy full message
Each assistant message has a **Copy** button (visible on hover) that copies the entire message content.

### 1.8 Edit and resend (message rewind)
Any past user message can be edited and resent. Hovering over a user message reveals a **pencil icon**. Clicking it opens an inline editor pre-filled with the original message. The user can modify the text and click **Resend** (or `Ctrl+Enter`). This truncates the conversation from that point onward and streams a new response — effectively branching the conversation from the edited message.

### 1.9 Response timings
After each complete response, a small badge shows the time-to-first-byte (TTFB) and total response time in milliseconds.

---

## 2. Conversations

### 2.1 New conversation
A **New conversation** button (pencil icon in the top bar, or `+` in the sidebar) starts a fresh chat.

### 2.2 Auto-naming
Conversations are automatically named after the first user message (truncated to 60 characters). The name appears in the sidebar and history table.

### 2.3 Rename conversation
Conversations can be renamed inline. In the sidebar, clicking the pencil icon next to a conversation name opens an inline text field. In the history table, the same pencil icon is always visible. Pressing `Enter` commits, `Escape` cancels.

### 2.4 Delete conversation
Any conversation can be deleted. A confirmation modal prevents accidental deletion. Deleting removes the conversation and all its messages permanently.

### 2.5 Resume conversation
Clicking a conversation in the sidebar or history table reopens it with its full message history.

---

## 3. Conversation History

### 3.1 History table
A dedicated `/history` page lists all conversations in a paginated table with the following columns:
- **Name** — the conversation name (or a truncated ID if unnamed), linking to the conversation
- **First message** — a preview of the opening user message
- **Created** — creation date
- **Last activity** — date of the most recent message

### 3.2 Pagination
The history table paginates at 20 conversations per page, with numbered page buttons and previous/next arrows.

### 3.3 Inline rename from history
The pencil icon in the history table allows renaming directly without navigating to the conversation.

### 3.4 Delete from history
The trash icon in the history table opens a confirmation modal and deletes the conversation.

---

## 4. Sidebar

### 4.1 Conversation list
A collapsible sidebar lists recent conversations, ordered by most recently created. Clicking a conversation navigates to it.

### 4.2 Toggle sidebar
A **panel icon** in the top bar shows or hides the sidebar.

### 4.3 Active conversation highlight
The currently open conversation is highlighted in the sidebar.

---

## 5. Assistants (Prompts)

### 5.1 Multiple assistants
The application supports multiple AI personas, each with a distinct system prompt. Assistants are defined as Markdown files in a `prompts/` directory and stored in the database on startup.

### 5.2 Assistant selector
A **dropdown** in the top bar of the chat interface lets the user switch between available assistants before or during a conversation. The selected assistant is applied to each new message sent.

### 5.3 Persisted prompt library
Prompts are stored in the database and served via `GET /prompts`. New assistants can be added by dropping a `.md` file into the `prompts/` directory and restarting the service — no code changes required.

**Current assistants:**
- **Default Assistant** — general-purpose concise assistant
- **Conflict Coach** — helps reason calmly through workplace conflicts
- **TypeScript Mentor** — teaches TypeScript from first principles

### 5.4 Per-prompt model preference
Each assistant can declare a preferred OpenAI model via a `model:` field in its `.md` frontmatter (e.g. `model: gpt-4o-mini`). When set, that model is used for all conversations with that assistant unless overridden per-request.

---

## 6. Model Selection

### 6.1 Model registry
A static registry of supported OpenAI models is served via `GET /models`. Each entry has a `slug` (the OpenAI model ID) and a human-readable `name`.

### 6.2 Per-request model override
API callers can pass `model_slug` in any conversation request body to override the model for that specific request. Resolution priority (highest → lowest):
1. `model_slug` in the request body
2. `model` field on the selected prompt
3. Global `settings.openai_model` (default)

Passing an unknown `model_slug` returns a 400 error.

---

## 7. Admin

### 6.1 Admin panel
A dedicated `/admin` section exists for managing prompts (system-level configuration). Currently read-only; full CRUD for prompts is a planned addition.

---

## Notes for UX Review

- **Rewind vs. edit history** — the rewind feature (§1.7) permanently deletes the tail of the conversation. There is no undo, and no way to view the "old" branch after rewinding. Consider whether users should be warned more explicitly, or whether soft-delete / branching history would be more forgiving.
- **Assistant switching mid-conversation** — the assistant selector changes which system prompt is used on the *next* message, but does not retroactively affect previous messages. The current conversation does not show which assistant was used for each turn. This may be confusing when switching mid-conversation.
- **Conversation naming** — auto-names are generated from the first user message only. If the first message is short or generic (e.g. "Hi"), the name won't be descriptive. Consider an option to regenerate the name, or to auto-name from an AI summary.
- **Stop button placement** — the Stop button currently replaces the entire input area during streaming. Consider whether it's better placed as an overlay or alongside the input to maintain visual continuity.
- **History vs. sidebar** — there are two entry points to past conversations (sidebar and `/history`). The sidebar is quick-access; the history page offers search-ready table layout. The relationship between the two is not currently explained to the user.
