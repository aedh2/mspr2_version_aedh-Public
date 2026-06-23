"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { buildBreadcrumbs } from "@/src/lib/routes";

export function Breadcrumb() {
  const pathname = usePathname() || "/";
  const crumbs = buildBreadcrumbs(pathname);

  if (crumbs.length === 0) return null;

  return (
    <nav className="breadcrumb" aria-label="Fil d'Ariane">
      <ol>
        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;
          return (
            <li key={crumb.href}>
              {isLast ? (
                <span aria-current="page">{crumb.label}</span>
              ) : (
                <Link href={crumb.href}>{crumb.label}</Link>
              )}
              {!isLast ? <ChevronRight size={14} aria-hidden /> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
