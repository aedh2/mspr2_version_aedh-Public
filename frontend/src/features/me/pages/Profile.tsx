"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Lock, Mail, Save, UserRound } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { Field, Input, Select } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { useAuth } from "@/src/features/auth/auth-provider";
import {
  activityOptions,
  budgetOptions,
  genreOptions,
  joinList,
  numberOrNull,
  objectiveOptions,
  splitList,
  sportLevelOptions
} from "@/src/features/me/profile-form-utils";
import { apiFormData, apiRequest } from "@/src/lib/api";
import { cleanPayload, UTILISATEUR_FIELDS } from "@/src/lib/payload";
import type { User } from "@/src/types/domain";
import { Page } from "./_shared";

const profileSchema = z.object({
  prenom: z.string().max(120).optional().or(z.literal("")),
  nom: z.string().max(120).optional().or(z.literal("")),
  nom_utilisateur: z.string().min(1).max(80),
  email: z.string().email().optional().or(z.literal("")),
  taille_cm: z.coerce.number().min(50).max(260).optional().or(z.literal("")),
  genre: z.string().max(20).optional().or(z.literal("")),
  date_naissance: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Format YYYY-MM-DD").optional().or(z.literal(""))
});
type ProfileFormValues = z.infer<typeof profileSchema>;

const passwordSchema = z.object({
  ancien_mot_de_passe: z.string().min(1, "Requis"),
  nouveau_mot_de_passe: z.string().min(8, "8 caracteres minimum"),
  confirmation: z.string().min(8, "Confirmation requise")
}).refine((data) => data.nouveau_mot_de_passe === data.confirmation, {
  path: ["confirmation"],
  message: "Les mots de passe ne correspondent pas"
});
type PasswordFormValues = z.infer<typeof passwordSchema>;
const AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp"];
const AVATAR_MAX_SIZE = 5 * 1024 * 1024;

const accompanimentSchema = z.object({
  prenom: z.string().min(1, "Prenom requis").max(120),
  nom: z.string().min(1, "Nom requis").max(120),
  date_naissance: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date requise"),
  genre: z.enum(["Inconnu", "Homme", "Femme", "Autre"]),
  taille_cm: z.coerce.number().min(50).max(260),
  poids_actuel_kg: z.coerce.number().min(20).max(350),
  poids_cible_kg: z.union([z.coerce.number().min(20).max(350), z.literal("")]).optional(),
  objectif_principal: z.string().min(1),
  date_cible: z.string().optional(),
  niveau_activite: z.enum(["sedentaire", "leger", "modere", "actif", "tres_actif"]),
  allergies: z.string().optional(),
  regime_alimentaire: z.string().optional(),
  preferences_alimentaires: z.string().optional(),
  aliments_evites: z.string().optional(),
  budget: z.enum(["", "faible", "moyen", "eleve"]),
  niveau_sportif: z.enum(["debutant", "intermediaire", "avance"]),
  equipements: z.string().optional(),
  contraintes_sante: z.string().optional(),
  preferences_sportives: z.string().optional(),
  frequence_seances_hebdo: z.coerce.number().min(0).max(14),
  duree_seance_min: z.coerce.number().min(5).max(240),
  duree_sommeil_h: z.coerce.number().min(0).max(24),
  qualite_sommeil_score: z.coerce.number().min(1).max(10)
});
type AccompanimentFormValues = z.infer<typeof accompanimentSchema>;

export function ProfilePage() {
  const [passwordOpen, setPasswordOpen] = useState(false);
  const profile = useQuery({
    queryKey: ["/api/me/profile"],
    queryFn: () => apiRequest<User>("/api/me/profile")
  });
  const user = profile.data;
  const initials = `${user?.prenom?.[0] || user?.nom_utilisateur?.[0] || "U"}${user?.nom?.[0] || ""}`.toUpperCase();

  if (profile.isLoading) return <LoadingState />;
  if (profile.isError) return <ErrorState message={profile.error.message} onRetry={() => profile.refetch()} />;
  if (!user) return <ErrorState message="Profil indisponible." onRetry={() => profile.refetch()} />;

  return (
    <Page title="Profil" eyebrow="Mon compte">
      <div className="profile-layout">
        <ChartCard title="Carte profil">
          <div className="profile-summary">
            <ProfileAvatarControl user={user} initials={initials} />
            <div className="profile-identity">
              <h3>{[user.prenom, user.nom].filter(Boolean).join(" ") || user.nom_utilisateur}</h3>
              <p className="muted">@{user.nom_utilisateur}</p>
              <div className="profile-badges">
                <span><Mail size={14} /> {user.email || "Email non renseigne"}</span>
                <span><UserRound size={14} /> {user.role}</span>
                <span><Building2 size={14} /> {user.organisation_nom || "Organisation non renseignee"}</span>
              </div>
            </div>
            <div className="profile-side-actions">
              <Button variant="secondary" onClick={() => setPasswordOpen(true)}>
                <Lock size={16} /> Modifier le mot de passe
              </Button>
            </div>
          </div>
        </ChartCard>

        <ProfileForm user={user} />
        <AccompanimentForm user={user} />
      </div>

      <PasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </Page>
  );
}

function AccompanimentForm({ user }: { user: User }) {
  const client = useQueryClient();
  const { refreshUser } = useAuth();
  const form = useForm<AccompanimentFormValues>({
    resolver: zodResolver(accompanimentSchema),
    defaultValues: {
      prenom: user.prenom || "",
      nom: user.nom || "",
      date_naissance: user.date_naissance ? user.date_naissance.slice(0, 10) : "",
      genre: (user.genre as AccompanimentFormValues["genre"]) || "Inconnu",
      taille_cm: user.taille_cm ?? undefined,
      poids_actuel_kg: user.poids_actuel_kg ?? undefined,
      poids_cible_kg: user.poids_cible_kg ?? "",
      objectif_principal: user.objectif_principal || "MAINTIEN_FORME",
      date_cible: user.date_cible ? user.date_cible.slice(0, 10) : "",
      niveau_activite: (user.niveau_activite as AccompanimentFormValues["niveau_activite"]) || "modere",
      allergies: joinList(user.allergies),
      regime_alimentaire: user.regime_alimentaire || "",
      preferences_alimentaires: joinList(user.preferences_alimentaires),
      aliments_evites: joinList(user.aliments_evites),
      budget: (user.budget_alimentaire as AccompanimentFormValues["budget"]) || "",
      niveau_sportif: (user.niveau_sportif as AccompanimentFormValues["niveau_sportif"]) || "debutant",
      equipements: joinList(user.equipements),
      contraintes_sante: joinList(user.contraintes_sante),
      preferences_sportives: joinList(user.preferences_sportives),
      frequence_seances_hebdo: user.frequence_seances_hebdo ?? 3,
      duree_seance_min: user.duree_seance_min ?? 45,
      duree_sommeil_h: user.duree_sommeil_h ?? 7,
      qualite_sommeil_score: user.qualite_sommeil_score ?? 7
    }
  });

  const mutation = useMutation({
    mutationFn: (values: AccompanimentFormValues) =>
      apiRequest<User>("/api/me/profile", {
        method: "PUT",
        body: {
          prenom: values.prenom,
          nom: values.nom,
          date_naissance: values.date_naissance,
          genre: values.genre,
          taille_cm: Number(values.taille_cm),
          poids_actuel_kg: Number(values.poids_actuel_kg),
          poids_cible_kg: numberOrNull(values.poids_cible_kg),
          objectif_principal: values.objectif_principal,
          date_cible: values.date_cible || null,
          niveau_activite: values.niveau_activite,
          allergies: splitList(values.allergies),
          regime_alimentaire: values.regime_alimentaire?.trim() || null,
          preferences_alimentaires: splitList(values.preferences_alimentaires),
          aliments_evites: splitList(values.aliments_evites),
          budget: values.budget || null,
          niveau_sportif: values.niveau_sportif,
          equipements: splitList(values.equipements),
          contraintes_sante: splitList(values.contraintes_sante),
          preferences_sportives: splitList(values.preferences_sportives),
          frequence_seances_hebdo: Number(values.frequence_seances_hebdo),
          duree_seance_min: Number(values.duree_seance_min),
          duree_sommeil_h: Number(values.duree_sommeil_h),
          qualite_sommeil_score: Number(values.qualite_sommeil_score)
        }
      }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["/api/me/profile"] });
      await client.invalidateQueries({ queryKey: ["me-dashboard"] });
      await refreshUser();
    }
  });

  return (
    <ChartCard title="Personnalisation HealthAI" subtitle="Ces valeurs alimentent le dashboard et les recommandations.">
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <div className="profile-form-grid">
          <Field label="Prenom" error={form.formState.errors.prenom?.message}>
            <Input {...form.register("prenom")} />
          </Field>
          <Field label="Nom" error={form.formState.errors.nom?.message}>
            <Input {...form.register("nom")} />
          </Field>
          <Field label="Date de naissance" error={form.formState.errors.date_naissance?.message}>
            <Input type="date" {...form.register("date_naissance")} />
          </Field>
          <Field label="Genre" error={form.formState.errors.genre?.message}>
            <Select {...form.register("genre")}>
              {genreOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </Field>
          <Field label="Taille (cm)" error={form.formState.errors.taille_cm?.message}>
            <Input type="number" step="0.1" {...form.register("taille_cm")} />
          </Field>
          <Field label="Poids actuel (kg)" error={form.formState.errors.poids_actuel_kg?.message}>
            <Input type="number" step="0.1" {...form.register("poids_actuel_kg")} />
          </Field>
          <Field label="Poids cible (kg)" error={form.formState.errors.poids_cible_kg?.message}>
            <Input type="number" step="0.1" {...form.register("poids_cible_kg")} />
          </Field>
          <Field label="Date cible" error={form.formState.errors.date_cible?.message}>
            <Input type="date" {...form.register("date_cible")} />
          </Field>
          <Field label="Objectif principal" error={form.formState.errors.objectif_principal?.message}>
            <Select {...form.register("objectif_principal")}>
              {objectiveOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </Field>
          <Field label="Niveau d'activite" error={form.formState.errors.niveau_activite?.message}>
            <Select {...form.register("niveau_activite")}>
              {activityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </Field>
          <Field label="Budget alimentaire" error={form.formState.errors.budget?.message}>
            <Select {...form.register("budget")}>
              {budgetOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </Field>
          <Field label="Niveau sportif" error={form.formState.errors.niveau_sportif?.message}>
            <Select {...form.register("niveau_sportif")}>
              {sportLevelOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </Field>
        </div>
        <Field label="Allergies" error={form.formState.errors.allergies?.message}>
          <Input placeholder="Ex: arachide, lactose" {...form.register("allergies")} />
        </Field>
        <Field label="Regime alimentaire" error={form.formState.errors.regime_alimentaire?.message}>
          <Input placeholder="Ex: vegetarien, sans gluten" {...form.register("regime_alimentaire")} />
        </Field>
        <div className="profile-form-grid">
          <Field label="Preferences alimentaires" error={form.formState.errors.preferences_alimentaires?.message}>
            <Input placeholder="Ex: riz, legumes" {...form.register("preferences_alimentaires")} />
          </Field>
          <Field label="Aliments evites" error={form.formState.errors.aliments_evites?.message}>
            <Input placeholder="Ex: thon, plats epices" {...form.register("aliments_evites")} />
          </Field>
          <Field label="Equipements disponibles" error={form.formState.errors.equipements?.message}>
            <Input placeholder="Ex: tapis, halteres" {...form.register("equipements")} />
          </Field>
          <Field label="Preferences sportives" error={form.formState.errors.preferences_sportives?.message}>
            <Input placeholder="Ex: gainage, mobilite" {...form.register("preferences_sportives")} />
          </Field>
          <Field label="Seances par semaine" error={form.formState.errors.frequence_seances_hebdo?.message}>
            <Input type="number" min="0" max="14" {...form.register("frequence_seances_hebdo")} />
          </Field>
          <Field label="Duree seance (min)" error={form.formState.errors.duree_seance_min?.message}>
            <Input type="number" min="5" max="240" {...form.register("duree_seance_min")} />
          </Field>
          <Field label="Sommeil (h/nuit)" error={form.formState.errors.duree_sommeil_h?.message}>
            <Input type="number" min="0" max="24" step="0.1" {...form.register("duree_sommeil_h")} />
          </Field>
          <Field label="Qualite sommeil /10" error={form.formState.errors.qualite_sommeil_score?.message}>
            <Input type="number" min="1" max="10" {...form.register("qualite_sommeil_score")} />
          </Field>
        </div>
        <Field label="Contraintes sante" error={form.formState.errors.contraintes_sante?.message}>
          <Input placeholder="Ex: douleur genou, hypertension" {...form.register("contraintes_sante")} />
        </Field>
        {mutation.isError ? <div className="form-error" role="alert">{mutation.error.message}</div> : null}
        {mutation.isSuccess ? <div className="form-success" role="status">Profil d'accompagnement mis a jour.</div> : null}
        <div className="form-actions">
          <Button type="submit" disabled={mutation.isPending || !form.formState.isDirty} aria-busy={mutation.isPending}>
            <Save size={16} />
            {mutation.isPending ? "Enregistrement..." : "Enregistrer l'accompagnement"}
          </Button>
        </div>
      </form>
    </ChartCard>
  );
}

function ProfileAvatarControl({ user, initials }: { user: User; initials: string }) {
  const client = useQueryClient();
  const { refreshUser } = useAuth();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const avatarUrl = user.photo_profil_url || null;

  useEffect(() => {
    setImageFailed(false);
  }, [avatarUrl]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return apiFormData<User>("/api/me/avatar", body, { method: user.photo_profil_url ? "PUT" : "POST" });
    },
    onSuccess: async (updatedUser) => {
      setLocalError(null);
      setMessage("Photo de profil mise a jour.");
      client.setQueryData(["/api/me/profile"], updatedUser);
      await client.invalidateQueries({ queryKey: ["/api/me/profile"] });
      await refreshUser();
    }
  });

  const busy = uploadMutation.isPending;

  const openFilePicker = () => {
    if (busy) return;
    setMessage(null);
    setLocalError(null);
    inputRef.current?.click();
  };

  const onFileSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setMessage(null);
    setLocalError(null);
    event.target.value = "";
    if (!file) return;
    if (!AVATAR_TYPES.includes(file.type)) {
      setLocalError("Format invalide. Utilisez JPG, PNG ou WebP.");
      return;
    }
    if (file.size > AVATAR_MAX_SIZE) {
      setLocalError("La photo doit faire 5 Mo maximum.");
      return;
    }
    uploadMutation.mutate(file);
  };

  return (
    <div className="profile-avatar-zone">
      <button
        type="button"
        className="profile-avatar profile-avatar-button"
        onClick={openFilePicker}
        aria-label={avatarUrl ? "Choisir une nouvelle photo de profil" : "Ajouter une photo de profil"}
        disabled={busy}
      >
        {avatarUrl && !imageFailed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt="" className="profile-avatar-image" onError={() => setImageFailed(true)} />
        ) : (
          <span>{initials}</span>
        )}
        {busy ? (
          <span className="profile-avatar-loader" aria-hidden>
            <Loader2 className="spin" size={18} />
          </span>
        ) : null}
      </button>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        disabled={busy}
        onChange={onFileSelected}
      />
      {message ? <div className="form-success profile-avatar-status" role="status">{message}</div> : null}
      {localError ? <div className="form-error profile-avatar-status" role="alert">{localError}</div> : null}
      {uploadMutation.isError ? <div className="form-error profile-avatar-status" role="alert">{uploadMutation.error.message}</div> : null}
    </div>
  );
}

function ProfileForm({ user }: { user: User }) {
  const client = useQueryClient();
  const { refreshUser } = useAuth();
  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    values: {
      prenom: user.prenom || "",
      nom: user.nom || "",
      nom_utilisateur: user.nom_utilisateur,
      email: user.email || "",
      taille_cm: (user.taille_cm ?? "") as number | "",
      genre: user.genre || "",
      date_naissance: user.date_naissance ? user.date_naissance.slice(0, 10) : ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      apiRequest("/api/me/profile", {
        method: "PUT",
        body: cleanPayload(values, UTILISATEUR_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/me/profile"] });
      client.invalidateQueries({ queryKey: ["me-dashboard"] });
      refreshUser();
    }
  });

  return (
    <ChartCard title="Informations personnelles">
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <div className="profile-form-grid">
          <Field label="Nom d'utilisateur" error={form.formState.errors.nom_utilisateur?.message}>
            <Input {...form.register("nom_utilisateur")} />
          </Field>
          <Field label="Email" error={form.formState.errors.email?.message}>
            <Input type="email" {...form.register("email")} />
          </Field>
          <Field label="Prenom">
            <Input {...form.register("prenom")} />
          </Field>
          <Field label="Nom">
            <Input {...form.register("nom")} />
          </Field>
          <Field label="Organisation">
            <Input value={user.organisation_nom || "Non renseignee"} readOnly />
          </Field>
          <Field label="Role">
            <Input value={user.role} readOnly />
          </Field>
          <Field label="Genre">
            <Select {...form.register("genre")}>
              <option value="">Non precise</option>
              <option value="Homme">Homme</option>
              <option value="Femme">Femme</option>
              <option value="Autre">Autre</option>
              <option value="Inconnu">Inconnu</option>
            </Select>
          </Field>
          <Field label="Taille (cm)" error={form.formState.errors.taille_cm?.message}>
            <Input type="number" step="0.1" {...form.register("taille_cm")} />
          </Field>
          <Field label="Date de naissance" error={form.formState.errors.date_naissance?.message}>
            <Input type="date" {...form.register("date_naissance")} />
          </Field>
          <Field label="Statut">
            <Input value={user.statut} readOnly />
          </Field>
        </div>
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        {mutation.isSuccess ? <div className="muted">Profil mis a jour.</div> : null}
        <div className="form-actions">
          <Button type="submit" disabled={mutation.isPending || !form.formState.isDirty}>
            <Save size={16} />
            {mutation.isPending ? "Enregistrement..." : "Enregistrer"}
          </Button>
        </div>
      </form>
    </ChartCard>
  );
}

function PasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const form = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { ancien_mot_de_passe: "", nouveau_mot_de_passe: "", confirmation: "" }
  });
  const mutation = useMutation({
    mutationFn: (values: PasswordFormValues) =>
      apiRequest("/api/me/password", {
        method: "PUT",
        body: {
          ancien_mot_de_passe: values.ancien_mot_de_passe,
          nouveau_mot_de_passe: values.nouveau_mot_de_passe
        }
      }),
    onSuccess: () => {
      form.reset();
      onClose();
    }
  });

  return (
    <Modal title="Modifier le mot de passe" open={open} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Mot de passe actuel" error={form.formState.errors.ancien_mot_de_passe?.message}>
          <Input type="password" autoComplete="current-password" {...form.register("ancien_mot_de_passe")} />
        </Field>
        <Field label="Nouveau mot de passe" error={form.formState.errors.nouveau_mot_de_passe?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("nouveau_mot_de_passe")} />
        </Field>
        <Field label="Confirmation" error={form.formState.errors.confirmation?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("confirmation")} />
        </Field>
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Mise a jour..." : "Mettre a jour"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
