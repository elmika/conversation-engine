"use client";

import { AdminTokenGate } from "@/components/admin/AdminTokenGate";
import { AdminHeader } from "@/components/admin/AdminHeader";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminTokenGate>
      <div className="h-full overflow-y-auto">
        <main className="mx-auto max-w-3xl px-4 py-8">
          <AdminHeader />
          {children}
        </main>
      </div>
    </AdminTokenGate>
  );
}
