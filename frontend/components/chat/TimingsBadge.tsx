import { Badge } from "@/components/ui/badge";
import type { Timings } from "@/lib/types";

interface TimingsBadgeProps {
  timings: Timings;
}

export function TimingsBadge({ timings }: TimingsBadgeProps) {
  return (
    <Badge variant="secondary" className="text-xs font-mono">
      TTFB: {timings.ttfb_ms}ms · Total: {timings.total_ms}ms
    </Badge>
  );
}
