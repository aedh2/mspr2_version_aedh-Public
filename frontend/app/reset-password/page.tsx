"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { HeartPulse } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { Field, Input } from "@/src/components/ui/forms";
import { apiRequest } from "@/src/lib/api";

const schema = z
  .object({
    token: z.string().min(1, "Token manquant"),
    mot_de_passe: z.string().min(8, "8 caracteres minimum"),
    confirmation: z.string().min(8)
  })
  .refine((data) => data.mot_de_passe === data.confirmation, {
    path: ["confirmation"],
    message: "Les mots de passe ne correspondent pas"
  });
type ResetForm = z.infer<typeof schema>;

function ResetPasswordInner() {
  const params = useSearchParams();
  const tokenFromUrl = params.get("token") || "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<ResetForm>({
    resolver: zodResolver(schema),
    defaultValues: { token: tokenFromUrl, mot_de_passe: "", confirmation: "" }
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await apiRequest("/api/auth/reset-password", {
        method: "POST",
        auth: false,
        body: {
          reset_token: values.token,
          nouveau_mot_de_passe: values.mot_de_passe
        }
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reinitialisation impossible.");
    }
  });

  return (
    <main className="login-screen">
      <section className="login-panel">
        <div className="brand login-brand">
          <HeartPulse size={24} />
          <div>
            <strong>HealthAI</strong>
            <span>Coaching</span>
          </div>
        </div>
        <div className="page-heading">
          <span className="eyebrow">Mot de passe</span>
          <h1>Definir un nouveau mot de passe</h1>
        </div>
        {done ? (
          <div className="form-stack">
            <p className="muted">Mot de passe mis a jour. Vous pouvez vous connecter.</p>
            <Link href="/login"><Button type="button">Aller a la connexion</Button></Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="form-stack">
            <Field label="Token" error={form.formState.errors.token?.message}>
              <Input {...form.register("token")} />
            </Field>
            <Field label="Nouveau mot de passe" error={form.formState.errors.mot_de_passe?.message}>
              <Input type="password" autoComplete="new-password" {...form.register("mot_de_passe")} />
            </Field>
            <Field label="Confirmation" error={form.formState.errors.confirmation?.message}>
              <Input type="password" autoComplete="new-password" {...form.register("confirmation")} />
            </Field>
            {error ? <div className="form-error">{error}</div> : null}
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Mise a jour..." : "Reinitialiser"}
            </Button>
            <Link href="/login" className="muted" style={{ textAlign: "center" }}>Retour connexion</Link>
          </form>
        )}
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordInner />
    </Suspense>
  );
}
