import { AdminConversationsTable } from "@/components/admin/AdminConversationsTable";

export default function AdminConversationsPage() {
  return (
    <section className="mt-6">
      <h2 className="mb-4 text-lg font-medium">All Conversations</h2>
      <AdminConversationsTable />
    </section>
  );
}
