"use client";

import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRenderPrompt } from "@/hooks/usePrompts";

interface PromptPreviewDialogProps {
  slug: string | null;
  onClose: () => void;
}

export function PromptPreviewDialog({ slug, onClose }: PromptPreviewDialogProps) {
  const { data, isPending, isError, error } = useRenderPrompt(slug);

  return (
    <Dialog open={!!slug} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Rendered Prompt Preview</DialogTitle>
        </DialogHeader>
        {isPending && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
        {isError && (
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : "Failed to load preview"}
          </p>
        )}
        {data && (
          <textarea
            readOnly
            className="min-h-[300px] w-full resize-y rounded-md border bg-muted p-3 font-mono text-xs leading-relaxed"
            value={data.rendered_prompt}
          />
        )}
        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
