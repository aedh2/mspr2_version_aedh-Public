"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Building2, Users } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { MetricCard } from "@/src/components/ui/cards";
import type { Column } from "@/src/components/ui/data-table";
import { Field, Input, Textarea } from "@/src/components/ui/forms";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { DataTable } from "@/src/components/ui/data-table";
import { apiRequest } from "@/src/lib/api";
import { apiList } from "@/src/lib/api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { Organisation, User } from "@/src/types/domain";
import { cleanPayload, ORGANISATION_FIELDS } from "@/src/lib/payload";
import { Page } from "@/src/features/admin/pages/_shared";

const orgSchema = z.object({
  nom: z.string().min(1),
  adresse: z.string().optional(),
  image_path: z.string().optional()
});
type OrgForm = z.infer<typeof orgSchema>;

export function SuperAdminOrganisationDetailPage({ organisationId }: { organisationId: number }) {
  const orgQuery = useQuery({
    queryKey: ["/api/organisations", organisationId],
    queryFn: () => apiRequest<Organisation>(`/api/organisations/${organisationId}`)
  });
  const usersQuery = useQuery({
    queryKey: ["/api/utilisateurs", { organisation_id: organisationId, page_size: 50 }],
    queryFn: () =>
      apiList<User>("/api/utilisateurs", { query: { organisation_id: organisationId, page_size: 50 } })
  });

  if (orgQuery.isLoading) return <LoadingState />;
  if (orgQuery.isError) return <ErrorState message={orgQuery.error.message} onRetry={() => orgQuery.refetch()} />;
  const org = orgQuery.data!;
  const users = usersQuery.data?.data || [];
  const total = usersQuery.data?.meta?.total ?? users.length;
  const admins = users.filter((u) => u.role === "ADMIN" || u.role === "SUPER_ADMIN").length;

  const columns: Column<User>[] = [
    { key: "id", header: "ID", render: (row) => row.utilisateur_id, align: "right" },
    {
      key: "name",
      header: "Utilisateur",
      render: (row) => (
        <Link className="row-link" href={`/admin/utilisateurs/${row.utilisateur_id}`}>
          {row.nom_utilisateur}
        </Link>
      )
    },
    { key: "email", header: "Email", render: (row) => row.email || "N/A" },
    { key: "role", header: "Role", render: (row) => row.role },
    { key: "statut", header: "Statut", render: (row) => row.statut }
  ];

  return (
    <Page title={org.nom} eyebrow="Super administration / organisation">
      <div className="metric-grid">
        <MetricCard label="Utilisateurs" value={formatNumber(total)} icon={Users} />
        <MetricCard label="Admins" value={formatNumber(admins)} icon={Building2} />
        <MetricCard label="Creee le" value={formatDate(org.cree_le)} icon={Building2} />
      </div>
      <OrganisationForm organisation={org} />
      <section className="page-section">
        <h2>Membres</h2>
        {usersQuery.isLoading ? <LoadingState /> : null}
        <DataTable rows={users} columns={columns} getRowKey={(row) => row.utilisateur_id} />
      </section>
    </Page>
  );
}

function OrganisationForm({ organisation }: { organisation: Organisation }) {
  const client = useQueryClient();
  const form = useForm<OrgForm>({
    resolver: zodResolver(orgSchema),
    values: {
      nom: organisation.nom,
      adresse: organisation.adresse || "",
      image_path: organisation.image_path || ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: OrgForm) =>
      apiRequest(`/api/organisations/${organisation.organisation_id}`, {
        method: "PATCH",
        body: cleanPayload(values, ORGANISATION_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/organisations"] });
    }
  });
  return (
    <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
      <Field label="Nom"><Input {...form.register("nom")} /></Field>
      <Field label="Adresse"><Textarea rows={3} {...form.register("adresse")} /></Field>
      <Field label="Image path"><Input {...form.register("image_path")} /></Field>
      {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
      {mutation.isSuccess ? <div className="muted">Enregistre.</div> : null}
      <div className="form-actions">
        <Button type="submit" disabled={mutation.isPending}>Enregistrer</Button>
      </div>
    </form>
  );
}
