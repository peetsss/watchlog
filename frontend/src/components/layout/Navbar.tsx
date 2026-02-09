"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Menu, X } from "lucide-react";
import { useState } from "react";
import SearchBar from "@/components/ui/SearchBar";
import type { NavTab } from "@/types";

const navItems: { label: string; href: string; tab: NavTab }[] = [
  { label: "Feed", href: "/feed", tab: "feed" },
  { label: "Discover", href: "/discover", tab: "discover" },
  { label: "Groups", href: "/groups", tab: "groups" },
  { label: "Lists", href: "/lists", tab: "lists" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const activeTab = navItems.find((item) => pathname.startsWith(item.href))?.tab;

  return (
    <nav
      className="relative z-10 border-b border-border bg-bg-primary/60 backdrop-blur-xl"
      data-testid="navbar"
    >
      <div className="mx-auto flex max-w-[1400px] items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link href="/feed" className="no-underline">
          <h1
            className="m-0 bg-gradient-to-r from-accent-orange via-accent-orange-light to-accent-teal bg-clip-text font-heading text-3xl tracking-[3px] text-transparent"
            data-testid="brand-logo"
          >
            CINECIRCLE
          </h1>
        </Link>

        {/* Desktop Nav */}
        <div className="hidden items-center gap-10 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.tab}
              href={item.href}
              className={`relative cursor-pointer border-none bg-none py-2 font-heading text-sm uppercase tracking-wider no-underline transition-all duration-300 ${
                activeTab === item.tab
                  ? "text-accent-orange"
                  : "text-text-muted hover:text-text-primary"
              }`}
              data-testid={`nav-${item.tab}`}
            >
              {item.label}
              {activeTab === item.tab && (
                <div className="animate-slide-in absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-accent-orange to-accent-orange-light" />
              )}
            </Link>
          ))}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-4">
          <div className="hidden sm:block">
            <SearchBar />
          </div>
          <button
            className="relative cursor-pointer border-none bg-none text-text-primary"
            data-testid="notification-bell"
          >
            <Bell size={20} />
            <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-accent-orange" />
          </button>

          {/* Mobile menu button */}
          <button
            className="cursor-pointer border-none bg-none text-text-primary md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            data-testid="mobile-menu-toggle"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile Nav */}
      {mobileMenuOpen && (
        <div className="border-t border-border bg-bg-primary/90 px-4 py-4 backdrop-blur-xl md:hidden">
          <div className="flex flex-col gap-4">
            {navItems.map((item) => (
              <Link
                key={item.tab}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`font-heading text-sm uppercase tracking-wider no-underline ${
                  activeTab === item.tab
                    ? "text-accent-orange"
                    : "text-text-muted"
                }`}
                data-testid={`mobile-nav-${item.tab}`}
              >
                {item.label}
              </Link>
            ))}
            <div className="pt-2 sm:hidden">
              <SearchBar />
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
