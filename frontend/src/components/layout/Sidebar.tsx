import { ChartColumnBig, LayoutDashboard, Moon, Send, Sun } from "lucide-react";
import { NavLink } from "react-router-dom";

import { Logo } from "@/components/ui/Logo";
import { FALLBACK_POLL_MS, useFeed, type FeedStatus } from "@/context/FeedContext";
import { useTheme } from "@/context/ThemeContext";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Queue", short: "Queue", icon: LayoutDashboard, end: true },
  { to: "/analytics", label: "Analytics", short: "Analytics", icon: ChartColumnBig, end: false },
  { to: "/submit", label: "Submit a ticket", short: "Submit", icon: Send, end: false },
] as const;

const FEED_STATE: Record<FeedStatus, { text: string; dot: string; hint: string }> = {
  live: { text: "Live", dot: "bg-low", hint: "Receiving tickets in real time" },
  connecting: { text: "Connecting", dot: "bg-medium", hint: "Opening the live feed" },
  offline: {
    text: "Polling",
    dot: "bg-fg-subtle",
    hint: `Live feed unavailable — refreshing every ${FALLBACK_POLL_MS / 1000}s`,
  },
};

function ThemeButton({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className={cn(
        "grid size-7 place-items-center rounded-md text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg",
        className,
      )}
    >
      {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

export function Sidebar() {
  const { status } = useFeed();
  const feed = FEED_STATE[status];

  return (
    <>
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-line bg-surface/60 backdrop-blur-xl md:flex">
        <div className="flex h-14 items-center px-5">
          <Logo />
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-3 py-2" aria-label="Primary">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "group flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-surface-2 text-fg shadow-[inset_0_0_0_1px_var(--line)]"
                    : "text-fg-muted hover:bg-surface-2/60 hover:text-fg",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn(
                      "size-4 transition-colors",
                      isActive ? "text-accent" : "text-fg-subtle group-hover:text-fg-muted",
                    )}
                  />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-1 border-t border-line p-3">
          <div className="flex items-center justify-between px-2 py-1" title={feed.hint}>
            <span className="flex items-center gap-2 text-xs text-fg-muted">
              <span className="relative flex size-2">
                {status === "live" && (
                  <span className={cn("absolute inset-0 animate-pulse-ring rounded-full", feed.dot)} />
                )}
                <span className={cn("relative size-2 rounded-full", feed.dot)} />
              </span>
              {feed.text}
            </span>
            <ThemeButton />
          </div>
        </div>
      </aside>

      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex h-14 items-stretch border-t border-line bg-surface/90 backdrop-blur-xl md:hidden"
        aria-label="Primary"
      >
        {NAV.map(({ to, short, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors",
                isActive ? "text-accent" : "text-fg-subtle",
              )
            }
          >
            <Icon className="size-4" />
            {short}
          </NavLink>
        ))}
        <div className="flex flex-1 items-center justify-center">
          <ThemeButton className="size-9" />
        </div>
      </nav>
    </>
  );
}
