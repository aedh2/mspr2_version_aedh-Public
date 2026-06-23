"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/src/components/ui/button";

export function EntityDrawer({
  title,
  open,
  onClose,
  children
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} role="presentation" />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="drawer-panel"
      >
        <header>
          <h2>{title}</h2>
          <Button variant="ghost" onClick={onClose} aria-label="Fermer">
            <X size={18} />
          </Button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </>
  );
}
