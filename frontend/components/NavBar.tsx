"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, History, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { getOrCreateUserId } from "@/lib/user-id";
import { getAdminToken, ADMIN_TOKEN_EVENT } from "@/lib/adminToken";

export function NavBar() {
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

  // Cosmetic only, not a security boundary — /admin's real gate (AdminTokenGate)
  // fully re-validates the token against the backend on every mount regardless
  // of what this tab shows. A stale token would show this tab briefly; that's
  // harmless and self-corrects the moment it's clicked into.
  const [hasAdminToken, setHasAdminToken] = useState(false);
  useEffect(() => {
    setHasAdminToken(!!getAdminToken());
    function onTokenChange() {
      setHasAdminToken(!!getAdminToken());
    }
    window.addEventListener(ADMIN_TOKEN_EVENT, onTokenChange);
    return () => window.removeEventListener(ADMIN_TOKEN_EVENT, onTokenChange);
  }, []);

  const TABS = [
    { label: "Chat", href: userId ? `/u/${userId}/chat` : "/", icon: MessageSquare },
    { label: "History", href: userId ? `/u/${userId}/history` : "/", icon: History },
    ...(hasAdminToken ? [{ label: "Admin", href: "/admin", icon: Settings }] : []),
  ];

  return (
    <nav className="flex border-b bg-background">
      {TABS.map(({ label, href, icon: Icon }) => {
        const isActive = pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={label}
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
