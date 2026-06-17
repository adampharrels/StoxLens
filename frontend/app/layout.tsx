import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export const metadata: Metadata = {
  title: "StoxLens",
  description: "Full-stack equity research tool"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="h-screen overflow-hidden bg-page text-primary">
          <Topbar />
          <div className="flex h-[calc(100vh-44px)]">
            <Sidebar />
            <main className="h-full flex-1 overflow-auto">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
