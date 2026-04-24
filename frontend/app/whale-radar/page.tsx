import { Suspense } from "react";
import WhaleRadarPage from "@/app/pages/whale-radar/WhaleRadarPage";

export default function WhaleRadarRoute() {
  return (
    <Suspense fallback={<div className="rounded-2xl border border-white/10 bg-card/50 p-10 text-muted-foreground">Loading Whale Radar...</div>}>
      <WhaleRadarPage />
    </Suspense>
  );
}
