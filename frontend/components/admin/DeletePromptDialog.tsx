"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useDeletePrompt } from "@/hooks/usePrompts";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";

interface DeletePromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  slug: string;
  name: string;
}

export function DeletePromptDialog({ open, onOpenChange, slug, name }: DeletePromptDialogProps) {
  const deleteMutation = useDeletePrompt();
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    setError(null);
    try {
      await deleteMutation.mutateAsync(slug);
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
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &ldquo;{name}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete the prompt. This action cannot be undone.
            {error && (
              <span className="mt-2 block text-destructive">{error}</span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
