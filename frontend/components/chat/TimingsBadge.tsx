import { Badge } from "@/components/ui/badge";
import type { Timings } from "@/lib/types";

interface TimingsBadgeProps {
  timings: Timings;
  model?: string | null;
}

export function TimingsBadge({ timings, model }: TimingsBadgeProps) {
  return (
    <Badge variant="secondary" className="text-xs font-mono">
      {model && <>{model} · </>}TTFB: {timings.ttfb_ms}ms · Total: {timings.total_ms}ms
    </Badge>
  );
}
