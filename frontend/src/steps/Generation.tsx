import { useEffect, useState } from "react";
import { etatJob, generer } from "../api";
import type { Job } from "../types";

export function Generation({
  session,
  pret,
  onTermine,
}: {
  session: string;
  pret: boolean;
  onTermine: (job: Job) => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!job || job.etat !== "en_cours") return;
    const timer = window.setInterval(async () => {
      try {
        const etat = await etatJob(session, job.job);
        setJob(etat);
        if (etat.etat === "termine") onTermine(etat);
        if (etat.etat === "erreur") setMessage(etat.message);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Le suivi du job a échoué.");
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [job, onTermine, session]);

  async function lancer() {
    setMessage(null);
    try {
      const cree = await generer(session);
      setJob({
        job: cree.job,
        etat: "en_cours",
        etape: "preparation",
        libelle: "Préparation du M et du DAX",
        progression: 5,
        niveau: null,
        message: null,
        erreur: null,
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "La génération n'a pas démarré.");
    }
  }

  return (
    <section className="space-y-4">
      <p className="text-sm leading-6">
        Un seul job : script M, DAX, TMDL, PBIR, compte rendu, puis ZIP. Le niveau A, B ou C est annoncé ici, avant le
        téléchargement. Le niveau A ne garantit pas l'ouverture dans Power BI Desktop.
      </p>
      <button
        type="button"
        className="rounded-full bg-pin px-5 py-2 text-sm font-semibold text-white"
        disabled={!pret || job?.etat === "en_cours"}
        onClick={lancer}
      >
        Lancer la génération
      </button>
      {job && (
        <div>
          <div className="mb-2 flex justify-between text-sm">
            <span>{job.libelle}</span>
            <span>{job.progression} %</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-filet" role="progressbar" aria-valuenow={job.progression} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-pin" style={{ width: `${job.progression}%` }} />
          </div>
          {job.etat === "termine" && (
            <p className="mt-4 rounded-xl bg-pin/10 px-4 py-3 text-sm">
              Niveau PBIR : <strong>{job.niveau}</strong>. {job.message}
            </p>
          )}
        </div>
      )}
      {message && <p className="rounded-xl bg-brique/10 px-4 py-3 text-sm">{message}</p>}
    </section>
  );
}
