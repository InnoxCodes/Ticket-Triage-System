import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { PageLoader } from "@/components/ui/PageLoader";
import { useAuth } from "@/context/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "checking") return <PageLoader />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
