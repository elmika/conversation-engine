"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { ArrowRight, X } from "lucide-react";
import type { SessionSummary } from "@/lib/types";

interface SessionSummaryCardProps {
  summary: SessionSummary;
  onStartNextSession: () => void;
  onClose: () => void;
}

export function SessionSummaryCard({ summary, onStartNextSession, onClose }: SessionSummaryCardProps) {
  return (
    <div className="rounded-lg border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-4">
        <div>
          {summary.course_name && (
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-0.5">
              {summary.course_name}
            </p>
          )}
          <h2 className="text-base font-semibold">Session complete</h2>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-muted-foreground" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {summary.modules.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
            Course modules
          </p>
          <ol className="space-y-0.5">
            {summary.modules.map((name, i) => (
              <li key={i} className="text-sm text-muted-foreground flex items-baseline gap-2">
                <span className="w-4 text-right shrink-0 font-mono text-xs">{i + 1}.</span>
                <span>{name}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {summary.next_step && (
        <div className="mb-5 rounded-md bg-muted/50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-1.5">
            Where to pick up next time
          </p>
          <div className="text-sm prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.next_step}</ReactMarkdown>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={onStartNextSession} size="sm" className="gap-1.5">
          <ArrowRight className="h-3.5 w-3.5" />
          Start next session
        </Button>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}
