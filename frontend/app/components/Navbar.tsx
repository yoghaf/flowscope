"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, ChevronDown, Search, Settings2, User, Zap } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const isActive = (path: string) => {
    if (path === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(path);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const search = query.trim();
    router.push(search ? `/scanner?search=${encodeURIComponent(search)}` : "/scanner");
  };

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!pathname.startsWith("/scanner")) {
      setQuery("");
      return;
    }
    const params = new URLSearchParams(window.location.search);
    setQuery(params.get("search") ?? "");
  }, [pathname]);

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    if (menuOpen) {
      document.addEventListener("mousedown", handleOutsideClick);
    }

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [menuOpen]);

  return (
    <nav className="sticky top-0 z-50 border-b border-white/5 bg-card/80 backdrop-blur-xl">
      <div className="mx-auto max-w-frame px-4 py-5 md:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <Link href="/" className="flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-primary/20 blur-xl" />
              <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/60">
                <Zap className="h-5 w-5 text-white" fill="currentColor" />
              </div>
            </div>
            <div>
              <span className="text-xl font-semibold tracking-tight text-foreground">FlowScope</span>
              <p className="text-[10px] text-muted-foreground">Pro Analytics</p>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            {[
              { href: "/", label: "Dashboard" },
              { href: "/scanner", label: "Scanner" },
              { href: "/whale-radar", label: "Whale Radar" },
              { href: "/performance", label: "Performance" },
              { href: "/signals", label: "AI Signals" },
              { href: "/demo-trading", label: "Demo Trade" },
              { href: "/alerts", label: "Alerts" },
              { href: "/alerts", label: "Alerts" },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-xl px-5 py-2.5 text-sm font-medium transition-all duration-200 ${
                  isActive(item.href)
                    ? "bg-primary/10 text-primary shadow-lg shadow-primary/20"
                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <form onSubmit={handleSubmit} className="relative">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search assets..."
                className="w-full rounded-xl border border-white/10 bg-white/5 py-2.5 pl-11 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50 sm:w-64"
              />
            </form>
            <Link
              href="/alerts"
              aria-label="Open alerts"
              className={`relative rounded-xl p-2.5 transition-all hover:bg-white/5 ${
                isActive("/alerts") ? "bg-primary/10 text-primary" : ""
              }`}
            >
              <Bell className="h-5 w-5 text-muted-foreground" />
              <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-primary" />
            </Link>
            <div ref={menuRef} className="relative">
              <button
                type="button"
                aria-label="Open quick menu"
                onClick={() => setMenuOpen((current) => !current)}
                className="flex items-center gap-2 rounded-xl p-2.5 transition-all hover:bg-white/5"
              >
                <User className="h-5 w-5 text-muted-foreground" />
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform ${menuOpen ? "rotate-180" : ""}`}
                />
              </button>
              {menuOpen ? (
                <div className="absolute right-0 top-full mt-2 w-56 rounded-2xl border border-white/10 bg-[#0B0F14] p-2 shadow-2xl shadow-black/40">
                  <div className="px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Quick Menu</p>
                  </div>
                  {[
                    { href: "/", label: "Open Dashboard" },
                    { href: "/scanner", label: "Open Scanner" },
                    { href: "/whale-radar", label: "Open Whale Radar" },
                    { href: "/performance", label: "Open Performance" },
                    { href: "/signals", label: "Open AI Signals" },
                    { href: "/demo-trading", label: "Open Demo Trade" },
                    { href: "/alerts", label: "Open Alerts" },
                    { href: "/alerts#alert-preferences", label: "Notification Settings", icon: Settings2 },
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMenuOpen(false)}
                        className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium text-foreground transition hover:bg-white/5 hover:text-primary"
                      >
                        <span>{item.label}</span>
                        {Icon ? <Icon className="h-4 w-4 text-muted-foreground" /> : null}
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
