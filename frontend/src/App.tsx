import { useState } from "react";
import { ErreurApi, deposer } from "./api";
import { StepBar } from "./components/StepBar";
import { Depot } from "./steps/Depot";
import { Generation } from "./steps/Generation";
import { Nettoyage } from "./steps/Nettoyage";
import { Telechargement } from "./steps/Telechargement";
import { Theme } from "./steps/Theme";
import type { Journal, Profil, ThemeReponse } from "./types";

export default function App() {
  const [etape, setEtape] = useState(0);
  const [session, setSession] = useState<string | null>(null);
  const [profil, setProfil] = useState<Profil | null>(null);
  const [lecture, setLecture] = useState(false);
  const [journal, setJournal] = useState<Journal | null>(null);
  const [theme, setTheme] = useState<ThemeReponse | null>(null);
  const [niveau, setNiveau] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  function signaler(error: unknown) {
    if (error instanceof ErreurApi && error.code === "session_expiree") {
      setSession(null);
      setProfil(null);
      setJournal(null);
      setTheme(null);
      setNiveau(null);
      setEtape(0);
      setErreur("La session a expiré. Déposez le fichier à nouveau.");
      return;
    }
    setErreur(error instanceof Error ? error.message : "Une erreur est survenue.");
  }

  async function onFichier(fichier: File) {
    setLecture(true);
    setErreur(null);
    setProfil(null);
    setJournal(null);
    setTheme(null);
    setNiveau(null);
    try {
      const resultat = await deposer(fichier);
      setSession(resultat.session);
      setProfil(resultat.profil);
    } catch (error) {
      signaler(error);
    } finally {
      setLecture(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-8 sm:px-6">
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.2em] text-pin">Atelier local</p>
        <h1 className="mt-2 font-serif text-4xl text-encre sm:text-5xl">Pack Power BI</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-encre/75">
          Déposez un CSV, choisissez trois à cinq couleurs, téléchargez un ZIP. Le site n'ouvre pas Power BI Desktop
          et n'envoie aucune ligne ailleurs.
        </p>
      </header>
      <StepBar courante={etape} />
      {erreur && (
        <p className="mt-6 rounded-xl bg-brique/10 px-4 py-3 text-sm" role="alert">
          {erreur}
        </p>
      )}
      <div className="mt-8">
        {etape === 0 && (
          <Depot
            session={session}
            profil={profil}
            lecture={lecture}
            onFichier={onFichier}
            onProfil={(id, suivant) => {
              setSession(id);
              setProfil(suivant);
              setJournal(null);
            }}
            onContinuer={() => setEtape(1)}
          />
        )}
        {etape === 1 && session && profil && (
          <Nettoyage
            session={session}
            profil={profil}
            onResultat={setJournal}
            onContinuer={() => setEtape(2)}
          />
        )}
        {etape === 2 && session && (
          <Theme
            session={session}
            onTheme={setTheme}
            onContinuer={() => setEtape(3)}
          />
        )}
        {etape === 3 && session && (
          <Generation
            session={session}
            pret={Boolean(journal && theme)}
            onTermine={(job) => {
              setNiveau(job.niveau);
              setDetail(job.message);
              setEtape(4);
            }}
          />
        )}
        {etape === 4 && session && niveau && (
          <Telechargement session={session} niveau={niveau} detail={detail} />
        )}
      </div>
    </main>
  );
}
