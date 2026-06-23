"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Field, Input, Select } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import type { Column } from "@/src/components/ui/data-table";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { useAuth } from "@/src/features/auth/auth-provider";
import type { Role, User } from "@/src/types/domain";
import { cleanPayload, UTILISATEUR_FIELDS } from "@/src/lib/payload";
import { CrudList, DeleteDialog, Page, RowActions } from "./_shared";

const userSchema = z.object({
  nom_utilisateur: z.string().min(1),
  prenom: z.string().optional(),
  nom: z.string().optional(),
  email: z.string().email().optional().or(z.literal("")),
  role: z.enum(["UTILISATEUR", "ADMIN", "SUPER_ADMIN"]),
  statut: z.string().min(1),
  organisation_id: z.union([z.string(), z.number()]).optional()
});
type UserForm = z.infer<typeof userSchema>;

export function UsersPage() {
  const router = useRouter();
  const [role, setRole] = useState("");
  const query = usePagedApi<User>("/api/utilisateurs", role ? { role } : {});
  const { user: currentUser } = useAuth();
  const rows = (query.data?.data || []).filter((row) => row.utilisateur_id !== currentUser?.utilisateur_id);
  useEffect(() => {
    query.setPage(1);
  }, [role]);
  const [editing, setEditing] = useState<User | null>(null);
  const [deleting, setDeleting] = useState<User | null>(null);
  const columns: Column<User>[] = [
    { key: "id", header: "ID", render: (row) => row.utilisateur_id, align: "right" },
    {
      key: "name",
      header: "Utilisateur",
      render: (row) => row.nom_utilisateur
    },
    { key: "email", header: "Email", render: (row) => row.email || "N/A" },
    { key: "role", header: "Role", render: (row) => <StatusBadge value={row.role} /> },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    {
      key: "open",
      header: "",
      align: "right",
      headerClassName: "row-open-cell",
      cellClassName: "row-open-cell",
      render: () => <span className="row-open-hint">Voir detail <ChevronRight size={14} /></span>
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => <RowActions onEdit={() => setEditing(row)} onDelete={() => setDeleting(row)} />
    }
  ];
  return (
    <Page title="Utilisateurs" eyebrow="Administration" actions={<Button onClick={() => setEditing({} as User)}>Creer</Button>}>
      <div className="filter-bar">
        <Select value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="">Tous les roles</option>
          <option value="UTILISATEUR">Utilisateur</option>
          <option value="ADMIN">Admin</option>
          <option value="SUPER_ADMIN">Super admin</option>
        </Select>
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.utilisateur_id} onRowClick={(row) => router.push(`/admin/utilisateurs/${row.utilisateur_id}`)} />
      <UserModal user={editing} onClose={() => setEditing(null)} />
      <DeleteDialog
        path="/api/utilisateurs"
        id={deleting?.utilisateur_id}
        label={deleting?.nom_utilisateur}
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
      />
    </Page>
  );
}

function UserModal({ user, onClose }: { user: User | null; onClose: () => void }) {
  const client = useQueryClient();
  const isNew = user && !user.utilisateur_id;
  const form = useForm<UserForm>({
    resolver: zodResolver(userSchema),
    values: {
      nom_utilisateur: user?.nom_utilisateur || "",
      prenom: user?.prenom || "",
      nom: user?.nom || "",
      email: user?.email || "",
      role: (user?.role || "UTILISATEUR") as Role,
      statut: user?.statut || "ACTIF",
      organisation_id: user?.organisation_id || ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: UserForm) =>
      apiRequest(`/api/utilisateurs${isNew ? "" : `/${user?.utilisateur_id}`}`, {
        method: isNew ? "POST" : "PATCH",
        body: cleanPayload(values, UTILISATEUR_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/utilisateurs"] });
      onClose();
    }
  });
  return (
    <Modal title={isNew ? "Creer un utilisateur" : "Modifier utilisateur"} open={Boolean(user)} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Nom utilisateur"><Input {...form.register("nom_utilisateur")} /></Field>
        <Field label="Prenom"><Input {...form.register("prenom")} /></Field>
        <Field label="Nom"><Input {...form.register("nom")} /></Field>
        <Field label="Email"><Input {...form.register("email")} /></Field>
        <Field label="Role">
          <Select {...form.register("role")}>
            <option value="UTILISATEUR">Utilisateur</option>
            <option value="ADMIN">Admin</option>
            <option value="SUPER_ADMIN">Super admin</option>
          </Select>
        </Field>
        <Field label="Statut"><Input {...form.register("statut")} /></Field>
        <Field label="Organisation ID"><Input type="number" {...form.register("organisation_id")} /></Field>
        {mutation.isError ? <div className="form-error">{mutation.error?.message || "Une erreur est survenue."}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}
