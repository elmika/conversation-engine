import { HistoryTable } from "@/components/history/HistoryTable";

interface Props {
  params: Promise<{ userId: string }>;
}

export default async function UserHistoryPage({ params }: Props) {
  const { userId } = await params;
  return (
    <div className="h-full overflow-y-auto">
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-6 text-2xl font-semibold">Conversation History</h1>
        <HistoryTable userId={userId} />
      </main>
    </div>
  );
}
