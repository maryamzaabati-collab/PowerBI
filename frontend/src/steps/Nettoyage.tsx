import { useMemo, useState } from "react";
import { nettoyer } from "../api";
import { ProfileTable } from "../components/ProfileTable";
import { REGLES_DEFAUT, ROLES, type Journal, type Profil, type Regles, type Role } from "../types";

export function Nettoyage({
  session,
  profil,
  onResultat,
  onContinuer,
}: {
  session: string;
  profil: Profil;
  onResultat: (journal: Journal) => void;
  onContinuer: () => void;
}) {
  const [regles, setRegles] = useState<Regles>(REGLES_DEFAUT);
  const [roles, setRoles] = useState<Record<string, Role>>(() =>
    Object.fromEntries(profil.colonnes.map((col) => [col.nom, col.role_propose])),
  );
  const temporelles = useMemo(
    () => profil.colonnes.filter((col) => roles[col.nom] === "temporel").map((col) => col.nom),
    [profil.colonnes, roles],
  );
  const [datePilote, setDatePilote] = useState<string>(temporelles[0] ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [apercu, setApercu] = useState<Profil["apercu"] | null>(null);
  const [journal, setJournal] = useState<Journal | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function appliquer() {
    setEnCours(true);
    setMessage(null);
    try {
      const resultat = await nettoyer(session, {
        regles,
        roles,
        date_pilote: temporelles.includes(datePilote) ? datePilote : temporelles[0] ?? null,
      });
      setJournal(resultat.journal);
      setApercu(resultat.apercu);
      onResultat(resultat.journal);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Le nettoyage a échoué.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-2 sm:grid-cols-2">
        {(
          [
            ["doublons", "Retirer les doublons de ligne exacts"],
            ["trim", "Trim, espaces insécables, largeur nulle"],
            ["vides", "Chaîne vide → manquant"],
            ["casse", "Harmoniser la casse des catégories"],
            ["nombres", "Convertir les nombres"],
            ["dates", "Lire les dates en jour/mois/année"],
          ] as const
        ).map(([cle, libelle]) => (
          <label key={cle} className="flex items-center gap-2 rounded-xl border border-filet bg-carte px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={regles[cle]}
              onChange={(event) => setRegles({ ...regles, [cle]: event.target.checked })}
            />
            {libelle}
          </label>
        ))}
      </div>
      <p className="text-sm text-encre/70">
        Aucune imputation : un numérique vide reste vide. Les aberrantes sont signalées, pas supprimées.
      </p>
      <div className="overflow-x-auto rounded-xl border border-filet">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-pin/10">
            <tr>
              <th className="px-3 py-2">Colonne</th>
              <th className="px-3 py-2">Rôle confirmé</th>
            </tr>
          </thead>
          <tbody>
            {profil.colonnes.map((col) => (
              <tr key={col.nom} className="border-t border-filet">
                <td className="px-3 py-2">{col.nom}</td>
                <td className="px-3 py-2">
                  <select
                    className="rounded-lg border border-filet bg-carte px-2 py-1"
                    value={roles[col.nom]}
                    onChange={(event) => setRoles({ ...roles, [col.nom]: event.target.value as Role })}
                  >
                    {ROLES.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.libelle}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {temporelles.length > 1 && (
        <label className="block text-sm">
          Date qui pilote le calendrier
          <select
            className="mt-1 block rounded-lg border border-filet bg-carte px-2 py-2"
            value={datePilote}
            onChange={(event) => setDatePilote(event.target.value)}
          >
            {temporelles.map((nom) => (
              <option key={nom}>{nom}</option>
            ))}
          </select>
        </label>
      )}
      {message && <p className="rounded-xl bg-brique/10 px-4 py-3 text-sm">{message}</p>}
      <button
        type="button"
        className="rounded-full bg-pin px-5 py-2 text-sm font-semibold text-white"
        disabled={enCours}
        onClick={appliquer}
      >
        {enCours ? "Nettoyage…" : "Appliquer le nettoyage"}
      </button>
      {journal && (
        <div className="space-y-3 text-sm">
          <p>
            {journal.lignes_avant} lignes avant, {journal.lignes_apres} après.
            {journal.dates_ambigues.length > 0 &&
              ` Dates ambiguës : ${journal.dates_ambigues.join(", ")}.`}
          </p>
          <ul className="space-y-1">
            {journal.regles.map((regle) => (
              <li key={regle.id}>
                {regle.libelle} — {regle.active ? "activée" : "désactivée"} ({regle.lignes_avant} → {regle.lignes_apres})
              </li>
            ))}
          </ul>
        </div>
      )}
      {apercu && <ProfileTable colonnes={profil.colonnes} apercu={apercu} />}
      {journal && (
        <button type="button" className="rounded-full bg-encre px-5 py-2 text-sm font-semibold text-papier" onClick={onContinuer}>
          Passer au thème
        </button>
      )}
    </section>
  );
}
