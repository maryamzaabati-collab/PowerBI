import { useEffect, useState } from "react";
import { ErreurApi, etatJob, generer } from "../api";
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
  const [demarrage, setDemarrage] = useState(false);

  const enCours = job?.etat === "en_cours";
  const jobId = job?.job;

  // Une requête de suivi à la fois (setTimeout enchaîné plutôt que setInterval),
  // et arrêt dès que le job se termine ou que le suivi échoue.
  useEffect(() => {
    if (!enCours || !jobId) return;
    let actif = true;
    let timer: number | undefined;
    let echecs = 0;

    async function suivre() {
      try {
        const etat = await etatJob(session, jobId!);
        if (!actif) return;
        echecs = 0;
        setJob(etat);
        if (etat.etat === "termine") onTermine(etat);
        if (etat.etat === "erreur") setMessage(etat.message);
        if (etat.etat === "en_cours") timer = window.setTimeout(suivre, 500);
      } catch (error) {
        if (!actif) return;
        echecs += 1;
        const definitif = (error instanceof ErreurApi && error.code === "session_expiree") || echecs >= 5;
        if (definitif) {
          setMessage(error instanceof Error ? error.message : "Le suivi du job a échoué.");
          setJob((avant) => (avant ? { ...avant, etat: "erreur" } : avant));
        } else {
          timer = window.setTimeout(suivre, 1000);
        }
      }
    }

    timer = window.setTimeout(suivre, 500);
    return () => {
      actif = false;
      window.clearTimeout(timer);
    };
  }, [enCours, jobId, onTermine, session]);

  async function lancer() {
    if (demarrage) return;
    setMessage(null);
    setDemarrage(true);
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
    } finally {
      setDemarrage(false);
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
        disabled={!pret || demarrage || job?.etat === "en_cours"}
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
