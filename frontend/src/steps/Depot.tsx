import { useState } from "react";
import { relire } from "../api";
import { DropZone } from "../components/DropZone";
import { ProfileTable } from "../components/ProfileTable";
import type { Profil } from "../types";

const ENCODAGES = [
  { id: "", libelle: "Détection proposée" },
  { id: "utf-8", libelle: "UTF-8" },
  { id: "utf-8-sig", libelle: "UTF-8 avec BOM" },
  { id: "cp1252", libelle: "Windows-1252" },
  { id: "latin-1", libelle: "Latin-1" },
];

const SEPARATEURS = [
  { id: "", libelle: "Détection proposée" },
  { id: ",", libelle: "Virgule" },
  { id: ";", libelle: "Point-virgule" },
  { id: "tab", libelle: "Tabulation" },
  { id: "|", libelle: "Barre verticale" },
];

export function Depot({
  session,
  profil,
  lecture,
  onFichier,
  onProfil,
  onContinuer,
}: {
  session: string | null;
  profil: Profil | null;
  lecture: boolean;
  onFichier: (fichier: File) => void;
  onProfil: (session: string, profil: Profil) => void;
  onContinuer: () => void;
}) {
  const [encodage, setEncodage] = useState("");
  const [separateur, setSeparateur] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function appliquer() {
    if (!session) return;
    setMessage(null);
    try {
      const resultat = await relire(session, encodage || undefined, separateur || undefined);
      onProfil(resultat.session, resultat.profil);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Relecture impossible.");
    }
  }

  return (
    <section className="space-y-6">
      {!profil && <DropZone occupé={lecture} onFichier={onFichier} />}
      {lecture && (
        <p className="rounded-xl bg-carte px-4 py-3 text-sm">Lecture du fichier. Le profil n'est pas encore définitif.</p>
      )}
      {profil && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Encodage
              <select
                className="mt-1 block rounded-lg border border-filet bg-carte px-2 py-2"
                value={encodage}
                onChange={(event) => setEncodage(event.target.value)}
              >
                {ENCODAGES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id ? item.libelle : `${item.libelle} (${profil.encodage})`}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Séparateur
              <select
                className="mt-1 block rounded-lg border border-filet bg-carte px-2 py-2"
                value={separateur}
                onChange={(event) => setSeparateur(event.target.value)}
              >
                {SEPARATEURS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id ? item.libelle : `${item.libelle} (${profil.separateur_libelle})`}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="rounded-full border border-filet px-4 py-2 text-sm" onClick={appliquer}>
              Relire
            </button>
            <label className="cursor-pointer text-sm text-pin">
              Changer de fichier
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={(event) => {
                  const fichier = event.target.files?.[0];
                  if (fichier) onFichier(fichier);
                }}
              />
            </label>
          </div>
          <p className="text-sm">
            {profil.lignes} lignes, {profil.colonnes_nombre} colonnes, {profil.doublons_exacts} doublons exacts
            après trim. Décimal candidat : {profil.decimal === "," ? "virgule" : "point"}.
          </p>
          {profil.avertissement_entete && (
            <p className="rounded-xl bg-brique/10 px-4 py-3 text-sm">{profil.avertissement_entete}</p>
          )}
          {message && <p className="rounded-xl bg-brique/10 px-4 py-3 text-sm">{message}</p>}
          <ProfileTable colonnes={profil.colonnes} apercu={profil.apercu} />
          <button type="button" className="rounded-full bg-pin px-5 py-2 text-sm font-semibold text-white" onClick={onContinuer}>
            Passer au nettoyage
          </button>
        </>
      )}
    </section>
  );
}
