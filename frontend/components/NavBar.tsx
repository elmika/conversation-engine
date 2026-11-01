"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { getOrCreateUserId } from "@/lib/user-id";

// Admin is a separate area, not a learner: /admin has its own header (AdminHeader) and
// must not mount the learner nav, whose useNavTabs() would mint a learner id for the
// admin's browser and offer Chat/History for it. The learner app doesn't link to /admin.
export function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

// Shared by the top NavBar (desktop) and BottomNav (mobile) so both surfaces
// stay in sync on labels/hrefs/icons/active-state logic.
export function useNavTabs() {
  const pathname = usePathname();

  // Prefer the userId already in the URL (instant, no flash). Only bare/legacy
  // pages (/, /chat, /history, 404s) lack one — for those, resolve the learner's
  // stored id client-side once mounted (localStorage isn't available at SSR/first
  // paint). Until resolved, Chat/History fall back to "/", which itself redirects
  // to the canonical /u/{userId}/chat — never a bare, side-effect-triggering route.
  const pathUserId = pathname.match(/^\/u\/([^/]+)/)?.[1];
  const [storedUserId, setStoredUserId] = useState<string | null>(null);
  useEffect(() => {
    if (!pathUserId) setStoredUserId(getOrCreateUserId());
  }, [pathUserId]);
  const userId = pathUserId ?? storedUserId;

  const tabs = [
    { label: "Chat", href: userId ? `/u/${userId}/chat` : "/", icon: MessageSquare },
    { label: "History", href: userId ? `/u/${userId}/history` : "/", icon: History },
  ];

  return {
    tabs: tabs.map((tab) => ({
      ...tab,
      isActive: pathname === tab.href || pathname.startsWith(tab.href + "/"),
    })),
  };
}

export function NavBar() {
  return isAdminPath(usePathname()) ? null : <LearnerNavBar />;
}

function LearnerNavBar() {
  const { tabs } = useNavTabs();

  return (
    <nav className="hidden border-b bg-background md:flex">
      {tabs.map(({ label, href, icon: Icon, isActive }) => (
        <Link
          key={label}
          href={href}
          aria-current={isActive ? "page" : undefined}
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
      ))}
    </nav>
  );
}
