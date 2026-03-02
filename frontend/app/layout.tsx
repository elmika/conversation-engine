import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Conversation Engine",
  description: "AI-powered conversation interface",
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
            <div className="flex-1 overflow-hidden">
              {children}
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
