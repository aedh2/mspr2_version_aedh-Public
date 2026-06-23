"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { PageHeader } from "@/src/components/ui/page-header";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import type { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { cleanPayload, type CleanPayloadOptions } from "@/src/lib/payload";

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

export function ListPage<T>({
  title,
  eyebrow,
  subtitle,
  query,
  rows,
  columns,
  getRowKey,
  chart,
  iconSummary,
  filterBar,
  actions
}: {
  title: string;
  eyebrow: string;
  subtitle?: string;
  query: ReturnType<typeof usePagedApi<T>>;
  rows: T[];
  columns: Column<T>[];
  getRowKey: (row: T) => React.Key;
  chart?: React.ReactNode;
  iconSummary?: React.ReactNode;
  filterBar?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <Page title={title} eyebrow={eyebrow} subtitle={subtitle} actions={actions}>
      {filterBar}
      {iconSummary}
      {chart}
      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <DataTable rows={rows} columns={columns} getRowKey={getRowKey} />
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}
    </Page>
  );
}

export function AddEntryModal({
  open,
  onClose,
  title,
  path,
  invalidateKey,
  fields,
  initialValues,
  cleanOptions,
  onSuccess
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  path: string;
  invalidateKey: string;
  fields: {
    name: string;
    label: string;
    type?: string;
    step?: string;
    required?: boolean;
    readOnly?: boolean;
    options?: Array<{ label: string; value: string | number }>;
    placeholder?: string;
  }[];
  initialValues?: Record<string, string>;
  cleanOptions?: CleanPayloadOptions;
  onSuccess?: () => void;
}) {
  const client = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>(initialValues || {});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {
      setValues(initialValues || {});
      setError(null);
    }
  }, [initialValues, open]);
  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      Object.entries(values).forEach(([k, v]) => {
        if (v === "" || v === null || v === undefined) return;
        const f = fields.find((f) => f.name === k);
        if (f?.type === "number") body[k] = Number(v);
        else if (f?.type === "datetime-local" && v) body[k] = new Date(v).toISOString();
        else body[k] = v;
      });
      return apiRequest(path, { method: "POST", body: cleanPayload(body, cleanOptions) });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: [invalidateKey] });
      client.invalidateQueries();
      setValues(initialValues || {});
      setError(null);
      onSuccess?.();
      onClose();
    },
    onError: (err: Error) => setError(err.message)
  });
  return (
    <Modal title={title} open={open} onClose={onClose}>
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        {fields.map((f) => (
          <Field key={f.name} label={f.label + (f.required ? " *" : "")}>
            {f.type === "textarea" ? (
              <Textarea
                rows={4}
                required={f.required}
                readOnly={f.readOnly}
                placeholder={f.placeholder}
                value={values[f.name] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              />
            ) : f.options ? (
              <Select
                required={f.required}
                disabled={f.readOnly}
                value={values[f.name] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              >
                <option value="">{f.placeholder || "Selectionner..."}</option>
                {f.options.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </Select>
            ) : (
              <Input
                type={f.type || "text"}
                step={f.step}
                required={f.required}
                readOnly={f.readOnly}
                placeholder={f.placeholder}
                value={values[f.name] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              />
            )}
          </Field>
        ))}
        {error ? <div className="form-error">{error}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "..." : "Enregistrer"}</Button>
        </div>
      </form>
    </Modal>
  );
}
