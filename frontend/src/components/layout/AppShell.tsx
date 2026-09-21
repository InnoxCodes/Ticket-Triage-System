import { Suspense } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/Sidebar";
import { Skeleton } from "@/components/ui/Skeleton";
import { FeedProvider } from "@/context/FeedContext";

function ContentFallback() {
  return (
    <div className="space-y-5 p-6 lg:p-8" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-xl" />
    </div>
  );
}

export function AppShell() {
  return (
    <FeedProvider>
      <div className="flex min-h-dvh bg-canvas">
        <Sidebar />
        {/* Bottom padding clears the fixed mobile tab bar. */}
        <main className="min-w-0 flex-1 pb-16 md:pb-0">
          <Suspense fallback={<ContentFallback />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </FeedProvider>
  );
}
