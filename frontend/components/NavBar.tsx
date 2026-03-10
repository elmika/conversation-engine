"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, History, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "History", href: "/history", icon: History },
  { label: "Admin", href: "/admin", icon: Settings },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="flex border-b bg-background">
      {TABS.map(({ label, href, icon: Icon }) => {
        const isActive = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors hover:text-foreground",
              isActive
                ? "border-b-2 border-primary text-foreground"
                : "text-muted-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
