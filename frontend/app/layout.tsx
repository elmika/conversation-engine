import type { Metadata, Viewport } from "next";
import "./globals.css";
import Providers from "./providers";
import { NavBar } from "@/components/NavBar";
import { BottomNav } from "@/components/BottomNav";

export const metadata: Metadata = {
  title: "Conversation Engine",
  description: "AI-powered conversation interface",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-screen flex-col">
            <NavBar />
            <div className="flex-1 overflow-hidden pb-14 md:pb-0">
              {children}
            </div>
            <BottomNav />
          </div>
        </Providers>
      </body>
    </html>
  );
}
