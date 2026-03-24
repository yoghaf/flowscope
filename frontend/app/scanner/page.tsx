import { Suspense } from "react";

import ScannerPage from "@/app/pages/scanner/ScannerPage";

export default function ScannerRoute() {
  return (
    <Suspense fallback={<div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">Loading scanner...</div>}>
      <ScannerPage />
    </Suspense>
  );
}
