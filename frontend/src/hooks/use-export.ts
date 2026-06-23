"use client";

import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@/src/features/auth/auth-provider";
import { ApiClientError } from "@/src/lib/api";
import { apiUrl } from "@/src/lib/config";

function buildUrl(path: string) {
  const base = apiUrl.replace(/\/+$/, "");
  let normalized = path.startsWith("/") ? path : `/${path}`;
  if (base.endsWith("/api") && normalized.startsWith("/api/")) {
    normalized = normalized.slice(4);
  }
  return `${base}${normalized}`;
}

export type ExportDataset =
  | "utilisateurs"
  | "biometrie"
  | "sommeil"
  | "sport"
  | "nutrition"
  | "qualite"
  | "executions"
  | "lots"
  | "plats";

export function useExport() {
  const { accessToken } = useAuth();
  return useMutation({
    mutationFn: async (dataset: ExportDataset) => {
      const headers = new Headers({ Accept: "text/csv" });
      if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
      const response = await fetch(buildUrl(`/api/admin/exports/${dataset}`), {
        headers,
        credentials: "include"
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new ApiClientError(response.status, {
          code: "export_failed",
          message: text || `Echec export ${dataset}`
        });
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `${dataset}.csv`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      return filename;
    }
  });
}
