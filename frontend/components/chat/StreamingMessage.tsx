import ReactMarkdown from "react-markdown";

interface StreamingMessageProps {
  partialText: string;
}

export function StreamingMessage({ partialText }: StreamingMessageProps) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl bg-muted px-4 py-2 text-sm text-foreground">
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown>{partialText}</ReactMarkdown>
        </div>
        {/* Blinking cursor */}
        <span className="inline-block w-0.5 h-4 bg-foreground animate-pulse ml-0.5 align-middle" />
      </div>
    </div>
  );
}
