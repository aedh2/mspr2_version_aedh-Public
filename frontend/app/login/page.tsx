"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Activity, ArrowLeft, ArrowRight, Dumbbell, HeartPulse, Salad, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { destinationForRole, useAuth } from "@/src/features/auth/auth-provider";
import { activityOptions, objectiveOptions, splitList } from "@/src/features/me/profile-form-utils";
import { ApiClientError, apiRequest } from "@/src/lib/api";

const loginSchema = z.object({
  identifiant: z.string().min(1, "Identifiant requis"),
  mot_de_passe: z.string().min(1, "Mot de passe requis")
});

const todayIso = () => new Date().toISOString().slice(0, 10);
const isFutureDate = (value?: string) => !!value && new Date(value).getTime() > Date.now();
const decimalInput = (value: unknown) => {
  if (typeof value !== "string") return value;
  const normalized = value.trim().replace(",", ".");
  return normalized ? Number(normalized) : Number.NaN;
};

const signupSchema = z.object({
  nom_utilisateur: z.string().min(2, "Identifiant requis").max(120),
  email: z.string().min(1, "Email requis").email("Email invalide."),
  mot_de_passe: z.string()
    .min(8, "8 caracteres minimum.")
    .regex(/[a-z]/, "Ajoutez une minuscule.")
    .regex(/[A-Z]/, "Ajoutez une majuscule.")
    .regex(/[0-9]/, "Ajoutez un chiffre."),
  confirmation: z.string().min(8, "Confirmation requise."),
  prenom: z.string().min(1, "Prenom requis").max(120),
  nom: z.string().min(1, "Nom requis").max(120),
  taille_cm: z.number().min(50, "Minimum 50 cm").max(260, "Maximum 260 cm"),
  poids_actuel_kg: z.number().min(20, "Minimum 20 kg").max(350, "Maximum 350 kg"),
  poids_cible_kg: z.number().min(20, "Minimum 20 kg").max(350, "Maximum 350 kg"),
  date_cible: z.string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Date cible requise.")
    .refine(isFutureDate, "La date cible doit etre future."),
  objectif_principal: z.string().min(1, "Objectif requis"),
  niveau_activite: z.enum(["sedentaire", "leger", "modere", "actif", "tres_actif"]),
  allergies: z.string().min(1, "Renseignez vos allergies ou indiquez aucune."),
  regime_alimentaire: z.string().min(1, "Regime alimentaire requis."),
  contraintes_sante: z.string().min(1, "Renseignez vos contraintes ou indiquez aucune.")
}).refine((values) => values.mot_de_passe === values.confirmation, {
  path: ["confirmation"],
  message: "Les mots de passe ne correspondent pas."
}).refine((values) => {
  if (values.objectif_principal === "PERTE_POIDS") return values.poids_cible_kg < values.poids_actuel_kg;
  if (values.objectif_principal === "GAIN_MUSCLE") return values.poids_cible_kg > values.poids_actuel_kg;
  return true;
}, {
  path: ["poids_cible_kg"],
  message: "Le poids cible doit correspondre a l'objectif choisi."
});

type LoginForm = z.infer<typeof loginSchema>;
type SignupForm = z.infer<typeof signupSchema>;
type AuthMode = "login" | "signup";
type AvailabilityResponse = {
  nom_utilisateur_disponible?: boolean | null;
  email_disponible?: boolean | null;
  nom_utilisateur_compte_incomplet?: boolean;
  email_compte_incomplet?: boolean;
  nom_utilisateur_message?: string | null;
  email_message?: string | null;
};

const stepFields: Record<number, Array<keyof SignupForm>> = {
  1: ["nom_utilisateur", "email", "mot_de_passe", "confirmation", "prenom", "nom"],
  2: [
    "taille_cm",
    "poids_actuel_kg",
    "poids_cible_kg",
    "date_cible",
    "objectif_principal",
    "niveau_activite",
    "allergies",
    "regime_alimentaire",
    "contraintes_sante"
  ]
};

export default function LoginPage() {
  const { login, register: registerAccount, status, user } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [signupStep, setSignupStep] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);

  const loginForm = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifiant: "", mot_de_passe: "" }
  });
  const signupForm = useForm<SignupForm>({
    resolver: zodResolver(signupSchema),
    mode: "onBlur",
    defaultValues: {
      nom_utilisateur: "",
      email: "",
      mot_de_passe: "",
      confirmation: "",
      prenom: "",
      nom: "",
      taille_cm: undefined,
      poids_actuel_kg: undefined,
      poids_cible_kg: undefined,
      date_cible: "",
      objectif_principal: "MAINTIEN_FORME",
      niveau_activite: "modere",
      allergies: "",
      regime_alimentaire: "",
      contraintes_sante: ""
    }
  });

  useEffect(() => {
    if (status === "authenticated" && user) {
      window.location.assign(destinationForRole(user.role));
    }
  }, [status, user]);

  useEffect(() => {
    setError(null);
  }, [mode, signupStep]);

  const onLoginSubmit = loginForm.handleSubmit(async (values) => {
    setError(null);
    try {
      await login(values.identifiant, values.mot_de_passe);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connexion impossible.");
    }
  });

  const validateStep = async (step: number) => {
    const valid = await signupForm.trigger(stepFields[step], { shouldFocus: true });
    if (!valid) return false;
    if (step !== 1) return true;
    setCheckingAvailability(true);
    try {
      const values = signupForm.getValues();
      const availability = await apiRequest<AvailabilityResponse>("/api/auth/register-availability", {
        auth: false,
        query: { nom_utilisateur: values.nom_utilisateur, email: values.email }
      });
      if (availability.nom_utilisateur_disponible === false) {
        signupForm.setError("nom_utilisateur", {
          message: availability.nom_utilisateur_message || "Cet identifiant est deja utilise."
        });
        return false;
      }
      if (availability.email_disponible === false) {
        signupForm.setError("email", {
          message: availability.email_message || "Cet email est deja utilise."
        });
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification impossible.");
      return false;
    } finally {
      setCheckingAvailability(false);
    }
  };

  const goNext = async () => {
    if (checkingAvailability || signupForm.formState.isSubmitting) return;
    if (await validateStep(signupStep)) setSignupStep(2);
  };

  const onSignupSubmit = signupForm.handleSubmit(async (values) => {
    if (signupStep < 2) {
      await goNext();
      return;
    }
    setError(null);
    try {
      await registerAccount({
        nom_utilisateur: values.nom_utilisateur,
        email: values.email,
        mot_de_passe: values.mot_de_passe,
        confirmation: values.confirmation,
        prenom: values.prenom,
        nom: values.nom,
        taille_cm: Number(values.taille_cm),
        poids_actuel_kg: Number(values.poids_actuel_kg),
        poids_cible_kg: Number(values.poids_cible_kg),
        objectif_principal: values.objectif_principal,
        date_cible: values.date_cible,
        niveau_activite: values.niveau_activite,
        allergies: splitList(values.allergies),
        regime_alimentaire: values.regime_alimentaire.trim(),
        contraintes_sante: splitList(values.contraintes_sante)
      });
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === "username_taken" || err.code === "username_incomplete") {
          signupForm.setError("nom_utilisateur", { message: err.message });
          setSignupStep(1);
          return;
        }
        if (err.code === "email_taken" || err.code === "email_incomplete") {
          signupForm.setError("email", { message: err.message });
          setSignupStep(1);
          return;
        }
      }
      setError(err instanceof Error ? err.message : "Creation de compte impossible.");
    }
  });

  const isLogin = mode === "login";
  const busy = signupForm.formState.isSubmitting || checkingAvailability;
  const title = isLogin ? "Acces au tableau de bord" : `Etape ${signupStep}/2 - ${signupTitle(signupStep)}`;
  const subtitle = isLogin
    ? "Connectez-vous avec vos identifiants HealthAI."
    : "Le compte sera cree uniquement apres validation finale du profil sante.";

  return (
    <main className="login-screen">
      <div className="login-composition">
        <section className="login-story" aria-label="Presentation HealthAI Coach">
          <div className="brand">
            <span className="brand-mark">
              <HeartPulse size={24} aria-hidden />
            </span>
            <div>
              <strong>HealthAI</strong>
              <span>Coach</span>
            </div>
          </div>
          <div>
            <span className="eyebrow">Application sante personnelle</span>
            <h1>Coaching sante pilote par vos donnees</h1>
            <p>
              Suivez nutrition, activite, sommeil, objectifs, posture et recommandations dans un espace applicatif
              unique, avec des fallbacks lisibles quand une donnee manque.
            </p>
          </div>
          <div className="login-story-grid">
            <span><Salad size={17} aria-hidden /><strong>Nutrition</strong>Analyse repas et journal</span>
            <span><Dumbbell size={17} aria-hidden /><strong>Sport</strong>Seances et posture</span>
            <span><Activity size={17} aria-hidden /><strong>KPI</strong>Dashboard personnel</span>
          </div>
        </section>

        <section className="login-panel auth-panel">
          <div className="brand login-brand">
            <span className="brand-mark">
              <ShieldCheck size={24} aria-hidden />
            </span>
            <div>
              <strong>Connexion securisee</strong>
              <span>HealthAI Coach</span>
            </div>
          </div>
          <div className="page-heading">
            <span className="eyebrow">Authentification</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="auth-mode-toggle" role="tablist" aria-label="Choisir le mode d'authentification">
            <Button type="button" variant={isLogin ? "primary" : "secondary"} onClick={() => setMode("login")}>
              Se connecter
            </Button>
            <Button type="button" variant={!isLogin ? "primary" : "secondary"} onClick={() => setMode("signup")}>
              Creer un compte
            </Button>
          </div>

          {isLogin ? (
            <form onSubmit={onLoginSubmit} className="form-stack">
              <Field label="Identifiant" error={loginForm.formState.errors.identifiant?.message}>
                <Input autoComplete="username" {...loginForm.register("identifiant")} />
              </Field>
              <Field label="Mot de passe" error={loginForm.formState.errors.mot_de_passe?.message}>
                <Input type="password" autoComplete="current-password" {...loginForm.register("mot_de_passe")} />
              </Field>
              {error ? <div className="form-error" role="alert">{error}</div> : null}
              <Button type="submit" disabled={loginForm.formState.isSubmitting} aria-busy={loginForm.formState.isSubmitting}>
                {loginForm.formState.isSubmitting ? "Connexion..." : "Se connecter"}
              </Button>
              <Link href="/forgot-password" className="muted auth-link">
                Mot de passe oublie ?
              </Link>
              <button type="button" className="auth-switch-link" onClick={() => setMode("signup")}>
                Pas encore de compte ? Creer un compte
              </button>
            </form>
          ) : (
            <form onSubmit={onSignupSubmit} className="form-stack">
              <SignupProgress step={signupStep} />
              {signupStep === 1 ? <SignupAccount form={signupForm} /> : <SignupHealth form={signupForm} />}
              {error ? <div className="form-error" role="alert">{error}</div> : null}
              <div className="form-actions">
                <Button type="button" variant="secondary" disabled={busy || signupStep === 1} onClick={() => setSignupStep(1)}>
                  <ArrowLeft size={16} /> Precedent
                </Button>
                {signupStep < 2 ? (
                  <Button type="button" disabled={busy} aria-busy={checkingAvailability} onClick={goNext}>
                    {checkingAvailability ? "Verification..." : "Suivant"} <ArrowRight size={16} />
                  </Button>
                ) : (
                  <Button type="submit" disabled={busy} aria-busy={signupForm.formState.isSubmitting}>
                    {signupForm.formState.isSubmitting ? "Creation..." : "Creer mon compte"}
                  </Button>
                )}
              </div>
              <button type="button" className="auth-switch-link" onClick={() => setMode("login")}>
                Deja inscrit ? Se connecter
              </button>
            </form>
          )}
        </section>
      </div>
    </main>
  );
}

function signupTitle(step: number) {
  return step === 1 ? "Creation du compte" : "Profil sante";
}

function SignupProgress({ step }: { step: number }) {
  return (
    <div className="onboarding-progress" aria-label="Progression inscription">
      {[1, 2].map((item) => (
        <strong key={item} className={item === step ? "is-active" : ""}>
          Etape {item}/2
        </strong>
      ))}
    </div>
  );
}

function SignupAccount({ form }: { form: UseFormReturn<SignupForm> }) {
  return (
    <>
      <Field label="Identifiant" error={form.formState.errors.nom_utilisateur?.message}>
        <Input autoComplete="username" {...form.register("nom_utilisateur")} />
      </Field>
      <Field label="Email" error={form.formState.errors.email?.message}>
        <Input type="email" autoComplete="email" {...form.register("email")} />
      </Field>
      <div className="auth-form-grid">
        <Field label="Mot de passe" error={form.formState.errors.mot_de_passe?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("mot_de_passe")} />
        </Field>
        <Field label="Confirmation du mot de passe" error={form.formState.errors.confirmation?.message}>
          <Input type="password" autoComplete="new-password" {...form.register("confirmation")} />
        </Field>
      </div>
      <div className="auth-form-grid">
        <Field label="Prenom" error={form.formState.errors.prenom?.message}>
          <Input autoComplete="given-name" {...form.register("prenom")} />
        </Field>
        <Field label="Nom" error={form.formState.errors.nom?.message}>
          <Input autoComplete="family-name" {...form.register("nom")} />
        </Field>
      </div>
    </>
  );
}

function SignupHealth({ form }: { form: UseFormReturn<SignupForm> }) {
  return (
    <>
      <div className="auth-form-grid">
        <Field label="Taille (cm)" error={form.formState.errors.taille_cm?.message}>
          <Input inputMode="decimal" placeholder="155" {...form.register("taille_cm", { setValueAs: decimalInput })} />
        </Field>
        <Field label="Poids actuel (kg)" error={form.formState.errors.poids_actuel_kg?.message}>
          <Input inputMode="decimal" placeholder="55" {...form.register("poids_actuel_kg", { setValueAs: decimalInput })} />
        </Field>
      </div>
      <div className="auth-form-grid">
        <Field label="Poids cible (kg)" error={form.formState.errors.poids_cible_kg?.message}>
          <Input inputMode="decimal" placeholder="62,9" {...form.register("poids_cible_kg", { setValueAs: decimalInput })} />
        </Field>
        <Field label="Date cible" error={form.formState.errors.date_cible?.message}>
          <Input type="date" min={todayIso()} {...form.register("date_cible")} />
        </Field>
      </div>
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
      <Field label="Allergies" error={form.formState.errors.allergies?.message}>
        <Input placeholder="Ex: arachide, lactose, gluten ou aucune" {...form.register("allergies")} />
      </Field>
      <Field label="Regime alimentaire" error={form.formState.errors.regime_alimentaire?.message}>
        <Input placeholder="Ex: vegetarien, sans gluten, halal ou aucun" {...form.register("regime_alimentaire")} />
      </Field>
      <Field label="Contraintes sante" error={form.formState.errors.contraintes_sante?.message}>
        <Textarea rows={3} placeholder="Ex: douleur genou, hypertension ou aucune" {...form.register("contraintes_sante")} />
      </Field>
    </>
  );
}
