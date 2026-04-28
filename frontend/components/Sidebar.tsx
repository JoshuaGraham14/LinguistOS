"use client";

import {
  BookMarked,
  BookOpen,
  Home,
  Settings,
  User as UserIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { useProfile } from "@/lib/storage";

const NAV = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/words", label: "Words", icon: BookMarked },
  { href: "/learn", label: "Learn", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { profile, hydrated } = useProfile();
  const displayName =
    hydrated && profile.name.trim() ? profile.name.trim() : "Friend";

  return (
    <aside className="w-64 shrink-0 flex flex-col gap-3">
      <Link href="/" className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-5 flex items-center gap-3 hover:bg-white transition">
        <Image
          src="/logo.png"
          alt="LinguistOS"
          width={44}
          height={44}
          className="shrink-0"
          priority
        />
        <div>
          <div className="text-lg font-bold bg-gradient-to-r from-fuchsia-600 to-purple-600 bg-clip-text text-transparent leading-tight">
            LinguistOS
          </div>
          <div className="text-xs text-slate-500 mt-0.5">Learn Spanish</div>
        </div>
      </Link>

      <nav className="flex flex-col gap-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-2xl bg-white/80 backdrop-blur px-5 py-3 shadow-soft text-slate-700 transition hover:bg-white hover:shadow-card",
                active && "bg-white shadow-card text-slate-900 font-medium",
              )}
            >
              <Icon className="h-5 w-5 text-slate-500" strokeWidth={1.75} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <Link
        href="/settings"
        className="mt-auto rounded-2xl bg-white/80 backdrop-blur shadow-card p-3 flex items-center gap-3 hover:bg-white transition"
      >
        <div className="h-10 w-10 rounded-full bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center text-white shadow-md">
          <UserIcon className="h-5 w-5" strokeWidth={2} />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-slate-900 leading-tight truncate">
            {displayName}
          </div>
          <div className="text-xs text-slate-500">Edit profile</div>
        </div>
      </Link>
    </aside>
  );
}
