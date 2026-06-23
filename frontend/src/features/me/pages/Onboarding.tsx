"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Moon, Salad, Save, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { useAuth } from "@/src/features/auth/auth-provider";
import { apiRequest } from "@/src/lib/api";
import type { User } from "@/src/types/domain";
import { Page } from "./_shared";

const onboardingSchema = z.object({
  prenom: z.string().min(1, "Prenom requis").max(120),
  nom: z.string().min(1, "Nom requis").max(120),
  date_naissance: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date requise"),
  genre: z.enum(["Homme", "Femme", "Autre", "Inconnu"]),
  taille_cm: z.coerce.number().min(50, "Minimum 50 cm").max(260, "Maximum 260 cm"),
  poids_actuel_kg: z.coerce.number().min(20, "Minimum 20 kg").max(350, "Maximum 350 kg"),
  poids_cible_kg: z.union([z.coerce.number().min(20).max(350), z.literal("")]).optional(),
  objectif_principal: z.string().min(1, "Objectif requis"),
  niveau_activite: z.enum(["sedentaire", "leger", "modere", "actif", "tres_actif"]),
  niveau_sportif: z.enum(["debutant", "intermediaire", "avance"]),
  allergies: z.string().optional(),
  regime_alimentaire: z.string().optional(),
  preferences_alimentaires: z.string().optional(),
  aliments_evites: z.string().optional(),
  budget: z.enum(["", "faible", "moyen", "eleve"]),
  equipements: z.string().optional(),
  contraintes_sante: z.string().optional(),
  preferences_sportives: z.string().optional(),
  frequence_seances_hebdo: z.coerce.number().min(0).max(14),
  duree_seance_min: z.coerce.number().min(5).max(240),
  duree_sommeil_h: z.coerce.number().min(0).max(16),
  qualite_sommeil_score: z.coerce.number().min(0).max(10)
});

type OnboardingForm = z.infer<typeof onboardingSchema>;

export function OnboardingPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const form = useForm<OnboardingForm>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      prenom: user?.prenom || "",
      nom: user?.nom || "",
      date_naissance: user?.date_naissance ? user.date_naissance.slice(0, 10) : "",
      genre: (user?.genre as OnboardingForm["genre"]) || "Inconnu",
      taille_cm: user?.taille_cm ?? undefined,
      poids_actuel_kg: undefined,
      poids_cible_kg: "",
      objectif_principal: "PERTE_POIDS",
      niveau_activite: "modere",
      niveau_sportif: "debutant",
      allergies: "",
      regime_alimentaire: "",
      preferences_alimentaires: "",
      aliments_evites: "",
      budget: "",
      equipements: "",
      contraintes_sante: "",
      preferences_sportives: "",
      frequence_seances_hebdo: 3,
      duree_seance_min: 45,
      duree_sommeil_h: 7,
      qualite_sommeil_score: 7
    }
  });

  const mutation = useMutation({
    mutationFn: (values: OnboardingForm) =>
      apiRequest<User>("/api/me/onboarding", {
        method: "POST",
        body: {
          ...values,
          poids_cible_kg: values.poids_cible_kg === "" ? null : values.poids_cible_kg,
          allergies: splitList(values.allergies),
          preferences_alimentaires: splitList(values.preferences_alimentaires),
          aliments_evites: splitList(values.aliments_evites),
          equipements: splitList(values.equipements),
          contraintes_sante: splitList(values.contraintes_sante),
          preferences_sportives: splitList(values.preferences_sportives),
          budget: values.budget || null,
          regime_alimentaire: values.regime_alimentaire?.trim() || null
        }
      }),
    onSuccess: async () => {
      await refreshUser();
      router.replace("/me/dashboard");
    }
  });

  return (
    <Page
      title="Personnaliser mon accompagnement"
      eyebrow="Etape 2/2"
      subtitle="Ces informations alimentent votre dashboard et les recommandations sans dupliquer les donnees."
    >
      <div className="onboarding-progress" aria-label="Progression inscription">
        <span><CheckCircle2 size={16} aria-hidden /> Etape 1/2 Compte cree</span>
        <strong>Etape 2/2 Accompagnement</strong>
      </div>

      <form className="form-stack onboarding-form" onSubmit={form.handleSubmit((values) => !mutation.isPending && mutation.mutate(values))}>
        <div className="onboarding-grid">
          <ChartCard title="Profil et objectif">
            <div className="onboarding-card-title"><UserRound size={18} aria-hidden /> Identite</div>
            <div className="profile-form-grid">
              <Field label="Prenom" error={form.formState.errors.prenom?.message}>
                <Input autoComplete="given-name" {...form.register("prenom")} />
              </Field>
              <Field label="Nom" error={form.formState.errors.nom?.message}>
                <Input autoComplete="family-name" {...form.register("nom")} />
              </Field>
              <Field label="Naissance" error={form.formState.errors.date_naissance?.message}>
                <Input type="date" {...form.register("date_naissance")} />
              </Field>
              <Field label="Genre" error={form.formState.errors.genre?.message}>
                <Select {...form.register("genre")}>
                  <option value="Inconnu">Inconnu</option>
                  <option value="Homme">Homme</option>
                  <option value="Femme">Femme</option>
                  <option value="Autre">Autre</option>
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
              <Field label="Objectif principal" error={form.formState.errors.objectif_principal?.message}>
                <Select {...form.register("objectif_principal")}>
                  <option value="PERTE_POIDS">Perte de poids</option>
                  <option value="MAINTIEN_FORME">Maintien</option>
                  <option value="GAIN_MUSCLE">Prise de masse</option>
                  <option value="EQUILIBRE_VIE">Sante</option>
                  <option value="SOMMEIL">Sommeil</option>
                  <option value="AUTRE">Autre</option>
                </Select>
              </Field>
            </div>
          </ChartCard>

          <ChartCard title="Nutrition">
            <div className="onboarding-card-title"><Salad size={18} aria-hidden /> Contraintes alimentaires</div>
            <div className="profile-form-grid">
              <Field label="Niveau d'activite">
                <Select {...form.register("niveau_activite")}>
                  <option value="sedentaire">Sedentaire</option>
                  <option value="leger">Leger</option>
                  <option value="modere">Modere</option>
                  <option value="actif">Actif</option>
                  <option value="tres_actif">Tres actif</option>
                </Select>
              </Field>
              <Field label="Budget alimentaire">
                <Select {...form.register("budget")}>
                  <option value="">Non precise</option>
                  <option value="faible">Faible</option>
                  <option value="moyen">Moyen</option>
                  <option value="eleve">Eleve</option>
                </Select>
              </Field>
            </div>
            <Field label="Allergies">
              <Input placeholder="Ex: arachide, lactose, gluten" {...form.register("allergies")} />
            </Field>
            <Field label="Regime alimentaire">
              <Input placeholder="Ex: vegetarien, sans gluten, halal" {...form.register("regime_alimentaire")} />
            </Field>
            <Field label="Preferences alimentaires">
              <Input placeholder="Ex: riz, poulet, legumes" {...form.register("preferences_alimentaires")} />
            </Field>
            <Field label="Aliments evites">
              <Input placeholder="Ex: thon, plats epices" {...form.register("aliments_evites")} />
            </Field>
          </ChartCard>

          <ChartCard title="Sport et sommeil">
            <div className="onboarding-card-title"><Moon size={18} aria-hidden /> Rythme de vie</div>
            <div className="profile-form-grid">
              <Field label="Niveau sportif">
                <Select {...form.register("niveau_sportif")}>
                  <option value="debutant">Debutant</option>
                  <option value="intermediaire">Intermediaire</option>
                  <option value="avance">Avance</option>
                </Select>
              </Field>
              <Field label="Seances par semaine" error={form.formState.errors.frequence_seances_hebdo?.message}>
                <Input type="number" min={0} max={14} {...form.register("frequence_seances_hebdo")} />
              </Field>
              <Field label="Duree seance (min)" error={form.formState.errors.duree_seance_min?.message}>
                <Input type="number" min={5} max={240} {...form.register("duree_seance_min")} />
              </Field>
              <Field label="Sommeil (h/nuit)" error={form.formState.errors.duree_sommeil_h?.message}>
                <Input type="number" min={0} max={16} step="0.1" {...form.register("duree_sommeil_h")} />
              </Field>
              <Field label="Qualite sommeil /10" error={form.formState.errors.qualite_sommeil_score?.message}>
                <Input type="number" min={0} max={10} {...form.register("qualite_sommeil_score")} />
              </Field>
            </div>
            <Field label="Equipements disponibles">
              <Input placeholder="Ex: tapis, halteres, elastique" {...form.register("equipements")} />
            </Field>
            <Field label="Contraintes sante">
              <Textarea rows={3} placeholder="Ex: douleur genou, hypertension, dos sensible" {...form.register("contraintes_sante")} />
            </Field>
            <Field label="Preferences sportives">
              <Input placeholder="Ex: gainage, mobilite, bras" {...form.register("preferences_sportives")} />
            </Field>
          </ChartCard>
        </div>

        {mutation.isError ? <div className="form-error" role="alert">{mutation.error.message}</div> : null}
        <div className="form-actions onboarding-actions">
          <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
            {mutation.isPending ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            {mutation.isPending ? "Enregistrement..." : "Valider et acceder au dashboard"}
          </Button>
        </div>
      </form>
    </Page>
  );
}

function splitList(value?: string) {
  return (value || "")
    .replace(/\n/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
