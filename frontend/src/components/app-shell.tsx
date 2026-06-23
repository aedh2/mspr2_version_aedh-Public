"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HeartPulse, LogOut, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Breadcrumb } from "@/src/components/layout/Breadcrumb";
import { Button } from "@/src/components/ui/button";
import { useAuth } from "@/src/features/auth/auth-provider";
import { appNavigation, canAccessRole, type NavigationItem } from "@/src/lib/permissions";

type NavigationSection = {
  label: string;
  items: NavigationItem[];
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const visibleItems = appNavigation.filter((item) => canAccessRole(user?.role, item.roles));
  const sections = groupNavigation(visibleItems);
  const displayName = user?.prenom || user?.nom_utilisateur || "Utilisateur";
  const initials = initialsFor(user?.prenom, user?.nom, user?.nom_utilisateur);
  const avatarUrl = user?.photo_profil_url || null;

  useEffect(() => {
    if (!sidebarOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    document.body.classList.add("navigation-lock");
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.classList.remove("navigation-lock");
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [sidebarOpen]);

  return (
    <div className={`app-shell${sidebarOpen ? " sidebar-open" : ""}`}>
      {sidebarOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Fermer le menu"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}
      <aside className="sidebar" id="app-sidebar" aria-label="Navigation principale">
        <div className="sidebar-shell">
          <div className="sidebar-top">
            <div className="brand">
              <span className="brand-mark">
                <HeartPulse size={22} aria-hidden />
              </span>
              <div>
                <strong>HealthAI</strong>
                <span>Coach</span>
              </div>
            </div>
            <Button
              variant="ghost"
              className="button-icon sidebar-close"
              onClick={() => setSidebarOpen(false)}
              aria-label="Fermer la navigation"
            >
              <X size={18} />
            </Button>
          </div>

          <div className="sidebar-profile" aria-label="Utilisateur connecte">
            <AvatarBubble className="sidebar-avatar" src={avatarUrl} initials={initials} />
            <div>
              <strong>{displayName}</strong>
              <span>{user?.nom_utilisateur ? `@${user.nom_utilisateur}` : user?.role || "Session"}</span>
            </div>
          </div>

          <nav aria-label="Navigation principale">
            {sections.map((section) => (
              <div className="sidebar-section" key={section.label}>
                <span className="sidebar-section-label">{section.label}</span>
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`));
                  return (
                    <Link
                      key={item.href}
                      className={active ? "nav-link active" : "nav-link"}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setSidebarOpen(false)}
                    >
                      <Icon size={17} aria-hidden />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <span>Application sante, nutrition et sport</span>
            <span>Donnees reelles uniquement</span>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <Button
              variant="secondary"
              className="button-icon mobile-menu-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Ouvrir la navigation"
              aria-controls="app-sidebar"
              aria-expanded={sidebarOpen}
            >
              <Menu size={18} />
            </Button>
            <div>
              <span className="eyebrow">{user?.role}</span>
              <h1>{displayName}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <Button variant="secondary" onClick={logout}>
              <LogOut size={16} />
              Deconnexion
            </Button>
          </div>
        </header>
        <Breadcrumb />
        {children}
      </main>
    </div>
  );
}

function AvatarBubble({ className, src, initials }: { className: string; src: string | null; initials: string }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <span className={className} aria-hidden>
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" onError={() => setFailed(true)} />
      ) : (
        initials
      )}
    </span>
  );
}

function groupNavigation(items: NavigationItem[]): NavigationSection[] {
  const userItems = items.filter((item) => item.href.startsWith("/me"));
  const adminItems = items.filter((item) => item.href.startsWith("/admin"));
  const superAdminItems = items.filter((item) => item.href.startsWith("/super-admin"));
  return [
    userItems.length ? { label: "Espace utilisateur", items: userItems } : null,
    adminItems.length ? { label: "Administration", items: adminItems } : null,
    superAdminItems.length ? { label: "Super admin", items: superAdminItems } : null
  ].filter((section): section is NavigationSection => Boolean(section));
}

function initialsFor(prenom?: string | null, nom?: string | null, username?: string | null) {
  const source = [prenom, nom].filter(Boolean).join(" ").trim() || username || "HA";
  return source
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "HA";
}
