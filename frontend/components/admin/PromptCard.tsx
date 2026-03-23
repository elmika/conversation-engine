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
import { ChevronDown, ChevronUp, Eye, EyeOff, Pencil, Trash2 } from "lucide-react";
import type { Prompt } from "@/lib/types";

interface PromptCardProps {
  prompt: Prompt;
  onEdit?: (prompt: Prompt) => void;
  onDisable?: (slug: string) => void;
  onEnable?: (slug: string) => void;
  onDelete?: (prompt: Prompt) => void;
}

export function PromptCard({ prompt, onEdit, onDisable, onEnable, onDelete }: PromptCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isDisabled = !prompt.is_active;

  return (
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
            {isDisabled && onEnable ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onEnable(prompt.slug)}
                title="Enable prompt"
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
            ) : onDisable ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onDisable(prompt.slug)}
                title="Disable prompt"
              >
                <EyeOff className="h-3.5 w-3.5" />
              </Button>
            ) : null}
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
        <Button
          variant="ghost"
          size="sm"
          className="mb-2 h-auto p-0 text-xs text-muted-foreground"
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
        {expanded && (
          <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-xs leading-relaxed">
            {prompt.system_prompt}
          </pre>
        )}
      </CardContent>
    </Card>
  );
}
