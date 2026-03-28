"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, ChevronDown, ChevronUp, Clipboard, Copy, Eye, EyeOff, Loader2, Pencil, ScanText, Trash2 } from "lucide-react";
import { useDisablePrompt, useEnablePrompt } from "@/hooks/usePrompts";
import { PromptPreviewDialog } from "@/components/admin/PromptPreviewDialog";
import type { Prompt } from "@/lib/types";

interface PromptCardProps {
  prompt: Prompt;
  onEdit?: (prompt: Prompt) => void;
  onDuplicate?: (prompt: Prompt) => void;
  onDelete?: (prompt: Prompt) => void;
}

export function PromptCard({ prompt, onEdit, onDuplicate, onDelete }: PromptCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [previewSlug, setPreviewSlug] = useState<string | null>(null);
  const isDisabled = !prompt.is_active;

  const disableMutation = useDisablePrompt();
  const enableMutation = useEnablePrompt();
  const isToggling = disableMutation.isPending || enableMutation.isPending;

  function handleCopy() {
    navigator.clipboard.writeText(prompt.system_prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <>
    <PromptPreviewDialog slug={previewSlug} onClose={() => setPreviewSlug(null)} />
    <Card className={isDisabled ? "opacity-60" : undefined}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <CardTitle className="text-base truncate">{prompt.name}</CardTitle>
            {isDisabled && (
              <Badge variant="secondary" className="shrink-0 text-xs">Disabled</Badge>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {prompt.model && (
              <Badge variant="secondary" className="font-mono text-xs">
                {prompt.model}
              </Badge>
            )}
            <Badge variant="outline" className="font-mono text-xs">
              {prompt.slug}
            </Badge>
            {onEdit && !isDisabled && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onEdit(prompt)}
                title="Edit prompt"
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            {onDuplicate && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onDuplicate(prompt)}
                title="Duplicate prompt"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setPreviewSlug(prompt.slug)}
              title="Preview rendered prompt"
            >
              <ScanText className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={isToggling}
              onClick={() =>
                isDisabled
                  ? enableMutation.mutate(prompt.slug)
                  : disableMutation.mutate(prompt.slug)
              }
              title={isDisabled ? "Enable prompt" : "Disable prompt"}
            >
              {isToggling ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : isDisabled ? (
                <Eye className="h-3.5 w-3.5" />
              ) : (
                <EyeOff className="h-3.5 w-3.5" />
              )}
            </Button>
            {onDelete && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-destructive hover:text-destructive"
                onClick={() => onDelete(prompt)}
                title="Delete prompt"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 mb-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-auto p-0 text-xs text-muted-foreground"
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? (
              <>
                <ChevronUp className="mr-1 h-3 w-3" />
                Hide system prompt
              </>
            ) : (
              <>
                <ChevronDown className="mr-1 h-3 w-3" />
                Show system prompt
              </>
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-auto p-0 text-xs text-muted-foreground"
            onClick={handleCopy}
            title="Copy system prompt to clipboard"
          >
            {copied ? (
              <>
                <Check className="mr-1 h-3 w-3 text-green-600" />
                <span className="text-green-600">Copied</span>
              </>
            ) : (
              <>
                <Clipboard className="mr-1 h-3 w-3" />
                Copy
              </>
            )}
          </Button>
        </div>
        {expanded && (
          <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-xs leading-relaxed">
            {prompt.system_prompt}
          </pre>
        )}
      </CardContent>
    </Card>
    </>
  );
}
