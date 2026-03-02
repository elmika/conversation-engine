import { PromptCard } from "@/components/admin/PromptCard";
import { StatsPanel } from "@/components/admin/StatsPanel";

async function getPrompts() {
  const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";
  const res = await fetch(`${FASTAPI_URL}/prompts`, { cache: "no-store" });
  if (!res.ok) return [];
  const data = await res.json();
  return data.prompts ?? [];
}

export default async function AdminPage() {
  const prompts = await getPrompts();

  return (
    <div className="h-full overflow-y-auto">
    <main className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Admin</h1>

      <section className="mb-8">
        <h2 className="mb-4 text-lg font-medium">Prompts / Personas</h2>
        <div className="flex flex-col gap-4">
          {prompts.map(
            (p: { slug: string; name: string; system_prompt: string }) => (
              <PromptCard key={p.slug} prompt={p} />
            )
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium">System</h2>
        <StatsPanel />
      </section>
    </main>
    </div>
  );
}
