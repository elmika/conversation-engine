import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "./CodeBlock";

interface StreamingMessageProps {
  partialText: string;
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

export function StreamingMessage({ partialText }: StreamingMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-sm text-foreground">
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{partialText}</ReactMarkdown>
        </div>
        {/* Blinking cursor */}
        <span className="inline-block w-0.5 h-4 bg-foreground animate-pulse ml-0.5 align-middle" />
      </div>
    </div>
  );
}
