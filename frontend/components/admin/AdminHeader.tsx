"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { clearAdminToken } from "@/lib/adminToken";

const SUB_TABS = [
  { label: "Prompts", href: "/admin" },
  { label: "Conversations", href: "/admin/conversations" },
];

export function AdminHeader() {
  const pathname = usePathname();

  return (
    <div className="mb-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <Button variant="ghost" size="sm" onClick={() => clearAdminToken()}>
          <LogOut className="mr-1 h-4 w-4" />
          Log out
        </Button>
      </div>
      <nav className="flex gap-4 border-b">
        {SUB_TABS.map(({ label, href }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "px-1 pb-2 text-sm font-medium transition-colors",
                isActive
                  ? "border-b-2 border-primary text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
