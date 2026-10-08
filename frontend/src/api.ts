export class ErreurApi extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function lire<T>(reponse: Response): Promise<T> {
  if (!reponse.ok) {
    let code = "generation_echouee";
    let message = "La requête n'a pas abouti. Réessayez.";
    try {
      const corps = await reponse.json();
      code = corps.code ?? code;
      message = corps.message ?? message;
    } catch {
      message = "L'API locale ne répond pas comme prévu. Vérifiez qu'uvicorn tourne sur le port 8741.";
    }
    throw new ErreurApi(code, message);
  }
  if (reponse.status === 204) return undefined as T;
  return reponse.json() as Promise<T>;
}

export async function deposer(fichier: File, encodage?: string, separateur?: string) {
  const donnees = new FormData();
  donnees.append("fichier", fichier);
  const cree = await lire<{ session: string; profil: import("./types").Profil }>(
    await fetch("/api/sessions", { method: "POST", body: donnees }),
  );
  if (!encodage && !separateur) return cree;
  return relire(cree.session, encodage, separateur);
}

export async function relire(session: string, encodage?: string, separateur?: string) {
  return lire<{ session: string; profil: import("./types").Profil }>(
    await fetch(`/api/sessions/${session}/parse`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ encodage: encodage || null, separateur: separateur || null }),
    }),
  );
}

export async function nettoyer(
  session: string,
  corps: { regles: import("./types").Regles; roles: Record<string, string>; date_pilote: string | null },
) {
  return lire<{ journal: import("./types").Journal; apercu: import("./types").Apercu }>(
    await fetch(`/api/sessions/${session}/clean`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    }),
  );
}

export async function enregistrerTheme(session: string, couleurs: string[]) {
  return lire<import("./types").ThemeReponse>(
    await fetch(`/api/sessions/${session}/theme`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ couleurs }),
    }),
  );
}

export async function generer(session: string) {
  return lire<{ job: string }>(await fetch(`/api/sessions/${session}/generate`, { method: "POST" }));
}

export async function etatJob(session: string, job: string) {
  return lire<import("./types").Job>(await fetch(`/api/sessions/${session}/jobs/${job}`));
}

export function urlTelechargement(session: string) {
  return `/api/sessions/${session}/download`;
}
