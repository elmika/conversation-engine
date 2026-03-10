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
import { ChevronDown, ChevronUp } from "lucide-react";
import type { Prompt } from "@/lib/types";

interface PromptCardProps {
  prompt: Prompt;
}

export function PromptCard({ prompt }: PromptCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{prompt.name}</CardTitle>
          <Badge variant="outline" className="font-mono text-xs">
            {prompt.slug}
          </Badge>
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
