"use client";

import { Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OutlineReadyBarProps {
  onStart: () => void;
  isStarting: boolean;
}

// Shown right above the chat input once the setup flow has proposed a course outline.
// Testers at the ICW demo reviewed the outline and then stopped: the old "Let's start"
// button sat in the header, small and off-screen on mobile (docs/roadmap.md item 9).
// The outline prompt deliberately never points at the button, so the UI has to make
// the next step obvious on its own, while still leaving room to keep refining the outline.
export function OutlineReadyBar({ onStart, isStarting }: OutlineReadyBarProps) {
  return (
    <div className="mb-3 flex flex-col gap-2 rounded-md border border-primary/30 bg-primary/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm">
        <span className="font-medium">Happy with this course outline?</span>{" "}
        <span className="text-muted-foreground">Start your first lesson, or reply below to change it.</span>
      </p>
      <Button
        onClick={onStart}
        disabled={isStarting}
        className="shrink-0 gap-1.5"
        title="Confirm your course and start learning"
      >
        {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        {isStarting ? "Setting up…" : "Let's start"}
      </Button>
    </div>
  );
}
