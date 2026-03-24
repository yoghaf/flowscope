import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import Navbar from "@/app/components/Navbar";
import { Providers } from "@/app/providers";

export const metadata: Metadata = {
  title: "FlowScope",
  description: "Realtime crypto derivatives analytics dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">
        <Providers>
          <div className="min-h-screen bg-background">
            <Navbar />
            <main className="mx-auto max-w-frame px-4 py-8 md:px-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
