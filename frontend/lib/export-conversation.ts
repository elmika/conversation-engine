/**
 * Export a conversation to a single Markdown document that is friendly to both a
 * human reader and a machine parser.
 *
 * Shape: a YAML frontmatter block (machine-parseable metadata) followed by a
 * readable transcript with one heading per turn, and — if the session was
 * wrapped — the session summary appended at the end.
 */

import type { Message, SessionSummary } from "@/lib/types";

export interface ConversationExport {
  conversationId: string;
  name?: string | null;
  promptSlug?: string | null;
  createdAt?: string | null;
  endedAt?: string | null;
  messages: Message[];
  summary?: SessionSummary | null;
}

const ROLE_LABELS: Record<string, string> = {
  user: "Learner",
  assistant: "Tutor",
  system: "System",
};

function yamlValue(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "number") return String(v);
  // Quote strings to keep the frontmatter valid regardless of content.
  return JSON.stringify(v);
}

/** Build the Markdown document for a conversation. Pure — no DOM access. */
export function conversationToMarkdown(
  data: ConversationExport,
  exportedAt: string = new Date().toISOString(),
): string {
  const title = data.name?.trim() || "Conversation";

  const frontmatter = [
    "---",
    `conversation_id: ${yamlValue(data.conversationId)}`,
    `name: ${yamlValue(data.name ?? null)}`,
    `course_prompt: ${yamlValue(data.promptSlug ?? null)}`,
    `created_at: ${yamlValue(data.createdAt ?? null)}`,
    `ended_at: ${yamlValue(data.endedAt ?? null)}`,
    `exported_at: ${yamlValue(exportedAt)}`,
    `message_count: ${data.messages.length}`,
    "---",
  ].join("\n");

  const turns = data.messages.map((m) => {
    const label = ROLE_LABELS[m.role] ?? m.role;
    const when = m.created_at ? ` · ${m.created_at}` : "";
    return `### ${label}${when}\n\n${m.content.trim()}`;
  });

  const sections = [frontmatter, `# ${title}`, "## Transcript", ...turns];

  if (data.summary) {
    const s = data.summary;
    const summaryLines = ["## Session summary"];
    if (s.course_name) summaryLines.push(`**Course:** ${s.course_name}`);
    if (s.modules && s.modules.length > 0) {
      summaryLines.push("**Modules covered:**", ...s.modules.map((mod) => `- ${mod}`));
    }
    if (s.next_step) summaryLines.push(`**Where to pick up next time:** ${s.next_step}`);
    sections.push(summaryLines.join("\n"));
  }

  return sections.join("\n\n") + "\n";
}

/** A filesystem-friendly filename like `conversation-typescript-mentor-2c1f8a3e-20260625.md`. */
export function conversationFilename(
  data: Pick<ConversationExport, "conversationId" | "name">,
  now: Date = new Date(),
): string {
  const slug = (data.name ?? "conversation")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "conversation";
  const shortId = data.conversationId.slice(0, 8);
  const date = now.toISOString().slice(0, 10).replace(/-/g, "");
  return `conversation-${slug}-${shortId}-${date}.md`;
}

/** Trigger a browser download of `content` as `filename`. DOM side-effect. */
export function downloadTextFile(filename: string, content: string, mime = "text/markdown"): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
