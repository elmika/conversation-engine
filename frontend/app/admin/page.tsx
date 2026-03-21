"use client";

import { useState } from "react";
import { PromptCard } from "@/components/admin/PromptCard";
import { StatsPanel } from "@/components/admin/StatsPanel";
import { PromptDialog } from "@/components/admin/PromptDialog";
import { DeletePromptDialog } from "@/components/admin/DeletePromptDialog";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { usePrompts, useAllPrompts, useDisablePrompt, useEnablePrompt } from "@/hooks/usePrompts";
import type { Prompt } from "@/lib/types";

export default function AdminPage() {
  const [showAll, setShowAll] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editPrompt, setEditPrompt] = useState<Prompt | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Prompt | null>(null);

  const activeResult = usePrompts();
  const allResult = useAllPrompts();
  const { data, isLoading, isError } = showAll ? allResult : activeResult;

  const disableMutation = useDisablePrompt();
  const enableMutation = useEnablePrompt();

  function handleEdit(prompt: Prompt) {
    setEditPrompt(prompt);
    setDialogOpen(true);
  }

  function handleNewPrompt() {
    setEditPrompt(null);
    setDialogOpen(true);
  }

  function handleDialogClose(open: boolean) {
    setDialogOpen(open);
    if (!open) setEditPrompt(null);
  }

  return (
    <div className="h-full overflow-y-auto">
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="mb-6 text-2xl font-semibold">Admin</h1>

        <section className="mb-8">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-medium">Prompts / Personas</h2>
              <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={showAll}
                  onChange={(e) => setShowAll(e.target.checked)}
                  className="accent-primary"
                />
                Show disabled
              </label>
            </div>
            <Button size="sm" onClick={handleNewPrompt}>
              <Plus className="mr-1 h-4 w-4" />
              New Prompt
            </Button>
          </div>

          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {isError && <p className="text-sm text-destructive">Failed to load prompts.</p>}

          <div className="flex flex-col gap-4">
            {data?.prompts.map((p) => (
              <PromptCard
                key={p.slug}
                prompt={p}
                onEdit={handleEdit}
                onDisable={(slug) => disableMutation.mutate(slug)}
                onEnable={(slug) => enableMutation.mutate(slug)}
                onDelete={setDeleteTarget}
              />
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-4 text-lg font-medium">System</h2>
          <StatsPanel />
        </section>
      </main>

      <PromptDialog
        open={dialogOpen}
        onOpenChange={handleDialogClose}
        prompt={editPrompt}
      />

      {deleteTarget && (
        <DeletePromptDialog
          open={Boolean(deleteTarget)}
          onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
          slug={deleteTarget.slug}
          name={deleteTarget.name}
        />
      )}
    </div>
  );
}
