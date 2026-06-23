"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/src/components/ui/button";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { ConfirmDialog } from "@/src/components/ui/modal";
import { PageHeader } from "@/src/components/ui/page-header";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import type { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";

export function Page({
  title,
  eyebrow,
  subtitle,
  actions,
  children
}: {
  title: string;
  eyebrow: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="page-section">
      <PageHeader title={title} eyebrow={eyebrow} subtitle={subtitle} actions={actions} />
      {children}
    </section>
  );
}

export function CrudList<T>({
  query,
  rows,
  columns,
  getRowKey,
  onRowClick,
  rowClassName,
  emptyLabel
}: {
  query: ReturnType<typeof usePagedApi<T>>;
  rows: T[];
  columns: Column<T>[];
  getRowKey: (row: T) => React.Key;
  onRowClick?: (row: T) => void;
  rowClassName?: string;
  emptyLabel?: string;
}) {
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  return (
    <>
      <DataTable rows={rows} columns={columns} getRowKey={getRowKey} onRowClick={onRowClick} rowClassName={rowClassName} emptyLabel={emptyLabel} />
      <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
    </>
  );
}

export function RowActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="row-actions">
      <Button variant="secondary" onClick={(event) => { event.stopPropagation(); onEdit(); }}>Editer</Button>
      <Button variant="danger" onClick={(event) => { event.stopPropagation(); onDelete(); }}>Supprimer</Button>
    </div>
  );
}

export function DeleteDialog({
  path,
  id,
  label,
  open,
  onClose,
  onSuccess,
  onError
}: {
  path: string;
  id?: number;
  label?: string;
  open: boolean;
  onClose: () => void;
  onSuccess?: (payload: any) => void;
  onError?: (error: any) => void;
}) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => apiRequest(`${path}/${id}`, { method: "DELETE" }),
    onSuccess: (payload) => {
      client.invalidateQueries({ queryKey: [path] });
      client.invalidateQueries();
      mutation.reset();
      onSuccess?.(payload);
      onClose();
    },
    onError: (error) => {
      onError?.(error);
    }
  });
  return (
    <ConfirmDialog
      open={open}
      title="Confirmer la suppression"
      message={`Supprimer ${label || "cet element"} ?`}
      onCancel={onClose}
      onConfirm={() => mutation.mutate()}
      busy={mutation.isPending}
    />
  );
}

export function normalizeForm<T extends Record<string, unknown>>(values: T) {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== "" && value !== undefined));
}
