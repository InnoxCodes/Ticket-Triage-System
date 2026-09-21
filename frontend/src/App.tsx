import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { PageLoader } from "@/components/ui/PageLoader";
import { ThemedToaster } from "@/components/ui/ThemedToaster";
import { ThemeProvider } from "@/context/ThemeContext";
import { queryClient } from "@/lib/query";
import DashboardPage from "@/pages/DashboardPage";

// Recharts is the heaviest dependency and only analytics uses it, so that view
// ships as its own chunk. The customer form is a separate entry point entirely.
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage"));
const SubmitPage = lazy(() => import("@/pages/SubmitPage"));

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MotionConfig reducedMotion="user">
          <BrowserRouter>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/submit" element={<SubmitPage />} />
                <Route element={<AppShell />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
            <ThemedToaster />
          </BrowserRouter>
        </MotionConfig>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
