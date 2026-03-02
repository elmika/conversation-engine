import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StatsPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Statistics</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Aggregate token usage and model stats coming soon.
        </p>
      </CardContent>
    </Card>
  );
}
