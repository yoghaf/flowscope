"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Zap, ArrowRight, Loader2 } from "lucide-react";
import { verifyPin } from "@/app/actions/auth";

export default function LoginPage() {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (!pin) {
      setError("Please enter a PIN");
      return;
    }

    setIsLoading(true);
    
    try {
      const result = await verifyPin(pin);
      if (result.success) {
        // Redirect back to dashboard or previous page
        // Wait for cookie to be fully set
        setTimeout(() => {
          router.push("/");
          router.refresh();
        }, 300);
      } else {
        setError(result.error || "Authentication failed");
        setPin("");
      }
    } catch (err) {
      setError("An error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/60 shadow-lg shadow-primary/20">
            <Zap className="h-8 w-8 text-white" fill="currentColor" />
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Restricted Access</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter your admin PIN to access private tools
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-card/50 p-8 shadow-2xl backdrop-blur-xl">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="pin" className="mb-2 block text-sm font-medium text-foreground">
                Admin PIN Code
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Lock className="h-5 w-5 text-muted-foreground" />
                </div>
                <input
                  id="pin"
                  name="pin"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  className="block w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-10 pr-3 text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50 sm:text-lg"
                  placeholder="••••••"
                  disabled={isLoading}
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-rose-500/10 p-3 text-sm font-medium text-rose-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-primary/30 transition-all hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  Unlock Access
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
