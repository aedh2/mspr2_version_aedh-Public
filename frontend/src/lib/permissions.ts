import {
  Activity,
  Apple,
  Antenna,
  BarChart3,
  Building2,
  Camera,
  ClipboardCheck,
  Clock3,
  DatabaseZap,
  Download,
  Dumbbell,
  Globe,
  IdCard,
  Moon,
  Sparkles,
  ScrollText,
  Shield,
  UtensilsCrossed,
  Users,
  Weight
} from "lucide-react";
import type { ComponentType } from "react";
import type { Role } from "@/src/types/domain";

export type NavigationItem = {
  href: string;
  label: string;
  roles: Role[];
  icon: ComponentType<{ size?: number }>;
};

export const appNavigation: NavigationItem[] = [
  { href: "/me/dashboard", label: "Tableau de bord", roles: ["UTILISATEUR"], icon: BarChart3 },
  { href: "/me/recommandations", label: "Recommandations", roles: ["UTILISATEUR"], icon: Sparkles },
  { href: "/me/analyse-plat", label: "Analyse repas", roles: ["UTILISATEUR"], icon: Sparkles },
  { href: "/me/nutrition", label: "Plats", roles: ["UTILISATEUR"], icon: UtensilsCrossed },
  { href: "/me/coach-posture", label: "Coach posture", roles: ["UTILISATEUR"], icon: Dumbbell },
  { href: "/me/seances", label: "Seances", roles: ["UTILISATEUR"], icon: Activity },
  { href: "/me/profile", label: "Profil", roles: ["UTILISATEUR"], icon: IdCard },
  { href: "/me/mesures-biometriques", label: "Biometrie", roles: ["UTILISATEUR"], icon: Weight },
  { href: "/me/sommeil", label: "Sommeil", roles: ["UTILISATEUR"], icon: Moon },
  { href: "/me/historique", label: "Historique", roles: ["UTILISATEUR"], icon: Clock3 },
  { href: "/me/exercices", label: "Exercices", roles: ["UTILISATEUR"], icon: Dumbbell },
  { href: "/me/aliments", label: "Aliments", roles: ["UTILISATEUR"], icon: Apple },
  { href: "/me/photos", label: "Photos", roles: ["UTILISATEUR"], icon: Camera },
  { href: "/admin/dashboard", label: "Dashboard admin", roles: ["ADMIN", "SUPER_ADMIN"], icon: Shield },
  { href: "/admin/utilisateurs", label: "Utilisateurs", roles: ["ADMIN", "SUPER_ADMIN"], icon: Users },
  { href: "/admin/etl/executions", label: "Executions ETL", roles: ["ADMIN", "SUPER_ADMIN"], icon: DatabaseZap },
  { href: "/admin/etl/lots", label: "Lots ETL", roles: ["ADMIN", "SUPER_ADMIN"], icon: DatabaseZap },
  { href: "/admin/etl/compare", label: "Avant / Apres ETL", roles: ["ADMIN", "SUPER_ADMIN"], icon: DatabaseZap },
  { href: "/admin/qualite", label: "Controles qualite", roles: ["ADMIN", "SUPER_ADMIN"], icon: ClipboardCheck },
  { href: "/admin/aliments", label: "Catalogue aliments", roles: ["ADMIN", "SUPER_ADMIN"], icon: Apple },
  { href: "/admin/exercices", label: "Catalogue exercices", roles: ["ADMIN", "SUPER_ADMIN"], icon: Dumbbell },
  { href: "/admin/regles-qualite", label: "Regles qualite", roles: ["ADMIN", "SUPER_ADMIN"], icon: ScrollText },
  { href: "/admin/exports", label: "Exports", roles: ["ADMIN", "SUPER_ADMIN"], icon: Download },
  { href: "/super-admin/dashboard", label: "Dashboard global", roles: ["SUPER_ADMIN"], icon: Globe },
  { href: "/super-admin/organisations", label: "Organisations", roles: ["SUPER_ADMIN"], icon: Building2 },
  { href: "/super-admin/sources", label: "Sources", roles: ["SUPER_ADMIN"], icon: DatabaseZap },
  { href: "/super-admin/monitoring", label: "Monitoring", roles: ["SUPER_ADMIN"], icon: Antenna }
];

export function canAccessRole(role: Role | undefined, allowedRoles: Role[]) {
  return Boolean(role && allowedRoles.includes(role));
}

export function destinationForRole(role: Role) {
  if (role === "SUPER_ADMIN") return "/super-admin/dashboard";
  if (role === "ADMIN") return "/admin/dashboard";
  return "/me/dashboard";
}
