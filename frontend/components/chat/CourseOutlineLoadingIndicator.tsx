"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/**
 * Dedicated loading state for the course-outline-compile turn, which runs on a
 * slower frontier model and can legitimately take ~1-2 minutes (see
 * docs/roadmap.md item 1). A live elapsed counter is proof-of-life, so a long
 * wait reads as "still working" rather than "frozen" — the generic three-dot
 * indicator gives no such signal.
 */
export function CourseOutlineLoadingIndicator() {
  const startRef = useRef(Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-2 py-1">
      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      <div className="flex flex-col gap-0.5">
        <span className="text-sm">Compiling your personalised course…</span>
        <span className="text-xs text-muted-foreground">This can take a minute or two.</span>
      </div>
      <Badge variant="secondary" className="text-xs font-mono ml-1">
        {elapsedSeconds}s elapsed
      </Badge>
    </div>
  );
}
