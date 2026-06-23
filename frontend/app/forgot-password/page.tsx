"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { HeartPulse } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { Field, Input } from "@/src/components/ui/forms";
import { apiRequest } from "@/src/lib/api";

const schema = z.object({ email: z.string().email("Email invalide") });
type ForgotForm = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<ForgotForm>({ resolver: zodResolver(schema), defaultValues: { email: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await apiRequest("/api/auth/forgot-password", { method: "POST", auth: false, body: values });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Envoi impossible.");
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
          <h1>Reinitialisation</h1>
          <p>Saisissez votre email, un lien de reinitialisation vous sera envoye.</p>
        </div>
        {sent ? (
          <div className="form-stack">
            <p className="muted">Si l&apos;email existe, un lien a ete envoye.</p>
            <Link href="/login"><Button variant="secondary" type="button">Retour connexion</Button></Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="form-stack">
            <Field label="Email" error={form.formState.errors.email?.message}>
              <Input type="email" autoComplete="email" {...form.register("email")} />
            </Field>
            {error ? <div className="form-error">{error}</div> : null}
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Envoi..." : "Envoyer le lien"}
            </Button>
            <Link href="/login" className="muted" style={{ textAlign: "center" }}>Retour connexion</Link>
          </form>
        )}
      </section>
    </main>
  );
}
