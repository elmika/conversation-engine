"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useCreatePrompt, useUpdatePrompt } from "@/hooks/usePrompts";
import { useModels } from "@/hooks/useModels";
import { ApiError } from "@/lib/api-client";
import type { Prompt } from "@/lib/types";

interface PromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided the dialog is in edit mode; otherwise create mode. */
  prompt?: Prompt | null;
}

export function PromptDialog({ open, onOpenChange, prompt }: PromptDialogProps) {
  const isEdit = Boolean(prompt);

  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [model, setModel] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const { data: modelsData } = useModels();
  const createMutation = useCreatePrompt();
  const updateMutation = useUpdatePrompt();
  const isPending = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (open) {
      setSlug(prompt?.slug ?? "");
      setName(prompt?.name ?? "");
      setSystemPrompt(prompt?.system_prompt ?? "");
      setModel(prompt?.model ?? "");
      setError(null);
    }
  }, [open, prompt]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (isEdit && prompt) {
        await updateMutation.mutateAsync({
          slug: prompt.slug,
          body: { name, system_prompt: systemPrompt, model: model || null },
        });
      } else {
        await createMutation.mutateAsync({
          slug,
          name,
          system_prompt: systemPrompt,
          model: model || null,
        });
      }
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("An unexpected error occurred.");
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Prompt" : "New Prompt"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="slug">Slug</Label>
            {isEdit ? (
              <Badge variant="outline" className="w-fit font-mono text-xs">
                {prompt?.slug}
              </Badge>
            ) : (
              <Input
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="my-prompt-slug"
                pattern="^[a-z0-9][a-z0-9\-_]*$"
                required
                disabled={isPending}
              />
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Prompt"
              required
              disabled={isPending}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="system-prompt">System Prompt</Label>
            <Textarea
              id="system-prompt"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="You are a helpful assistant..."
              rows={5}
              required
              disabled={isPending}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="model">Model</Label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={isPending}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="">Default</option>
              {modelsData?.models.map((m) => (
                <option key={m.slug} value={m.slug}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isEdit ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
