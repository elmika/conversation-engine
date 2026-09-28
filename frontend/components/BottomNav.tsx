"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useNavTabs } from "@/components/NavBar";

export function BottomNav() {
  const { tabs } = useNavTabs();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden">
      {tabs.map(({ label, href, icon: Icon, isActive }) => (
        <Link
          key={label}
          href={href}
          aria-current={isActive ? "page" : undefined}
          className={cn(
            "flex min-h-11 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-xs font-medium transition-colors",
            isActive ? "text-primary" : "text-muted-foreground"
          )}
        >
          <Icon className="h-5 w-5" />
          {label}
        </Link>
      ))}
    </nav>
  );
}
