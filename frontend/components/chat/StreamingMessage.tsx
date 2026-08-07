import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./CodeBlock";
import { CourseOutlineLoadingIndicator } from "./CourseOutlineLoadingIndicator";

// Matches the flow id in app/domain/setup_flow.py — the one turn worth a
// dedicated "this may take a minute or two" loading state (see docs/roadmap.md item 3).
const COURSE_OUTLINE_PROMPT_SLUG = "course-outline-proposal";

interface StreamingMessageProps {
  partialText: string;
  promptSlug?: string | null;
}

const markdownComponents = {
  pre({ children }: { children?: React.ReactNode }) {
    return <>{children}</>;
  },
  code({ className, children }: { className?: string; children?: React.ReactNode }) {
    const match = /language-(\w+)/.exec(className || "");
    const codeString = String(children).replace(/\n$/, "");
    const isBlock = Boolean(match) || codeString.includes("\n");

    if (isBlock) {
      return <CodeBlock language={match?.[1] ?? ""} code={codeString} />;
    }
    return (
      <code className="bg-zinc-100 dark:bg-zinc-700 rounded px-1 py-0.5 text-xs font-mono">
        {children}
      </code>
    );
  },
};

export function StreamingMessage({ partialText, promptSlug }: StreamingMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-sm text-foreground">
        {partialText ? (
          <>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{partialText}</ReactMarkdown>
            </div>
            <span className="inline-block w-0.5 h-4 bg-foreground animate-pulse ml-0.5 align-middle" />
          </>
        ) : promptSlug === COURSE_OUTLINE_PROMPT_SLUG ? (
          <CourseOutlineLoadingIndicator />
        ) : (
          <div className="flex items-center gap-1 py-1">
            <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:0ms]" />
            <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:150ms]" />
            <span className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:300ms]" />
          </div>
        )}
      </div>
    </div>
  );
}
