import { useCallback, useState } from "react";
import { ErreurApi, deposer, oublier } from "./api";
import { StepBar } from "./components/StepBar";
import { Depot } from "./steps/Depot";
import { Generation } from "./steps/Generation";
import { Nettoyage } from "./steps/Nettoyage";
import { Telechargement } from "./steps/Telechargement";
import { Theme } from "./steps/Theme";
import type { Job, Journal, Profil, ThemeReponse } from "./types";

// Étapes : 0 Dépôt, 1 Nettoyage, 2 Thème, 3 Génération, 4 Téléchargement.
// Les étapes déjà visitées restent montées (cachées) pour garder leurs réglages
// quand on revient en arrière par la barre d'étapes.
export default function App() {
  const [etape, setEtape] = useState(0);
  const [atteinte, setAtteinte] = useState(0);
  const [session, setSession] = useState<string | null>(null);
  const [profil, setProfil] = useState<Profil | null>(null);
  const [versionProfil, setVersionProfil] = useState(0);
  const [versionGeneration, setVersionGeneration] = useState(0);
  const [lecture, setLecture] = useState(false);
  const [journal, setJournal] = useState<Journal | null>(null);
  const [theme, setTheme] = useState<ThemeReponse | null>(null);
  const [niveau, setNiveau] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  function aller(suivante: number) {
    setEtape(suivante);
    setAtteinte((avant) => Math.max(avant, suivante));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Le serveur efface le ZIP dès que le nettoyage, le thème ou la lecture changent :
  // la génération et le téléchargement doivent être refaits.
  function invaliderGeneration(plafond: number) {
    setNiveau(null);
    setDetail(null);
    setVersionGeneration((v) => v + 1);
    setAtteinte((avant) => Math.min(avant, plafond));
  }

  function toutOublier() {
    setSession(null);
    setProfil(null);
    setJournal(null);
    setTheme(null);
    setNiveau(null);
    setDetail(null);
    setEtape(0);
    setAtteinte(0);
    setVersionProfil((v) => v + 1);
    setVersionGeneration((v) => v + 1);
  }

  function signaler(error: unknown) {
    if (error instanceof ErreurApi && error.code === "session_expiree") {
      toutOublier();
      setErreur("La session a expiré. Déposez le fichier à nouveau.");
      return;
    }
    setErreur(error instanceof Error ? error.message : "Une erreur est survenue.");
  }

  async function onFichier(fichier: File) {
    const ancienne = session;
    setLecture(true);
    setErreur(null);
    toutOublier();
    if (ancienne) void oublier(ancienne).catch(() => undefined);
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

  const onJournal = useCallback((suivant: Journal | null) => {
    setJournal(suivant);
    invaliderGeneration(suivant ? 2 : 1);
  }, []);

  const onTheme = useCallback((suivant: ThemeReponse | null) => {
    setTheme(suivant);
    invaliderGeneration(suivant ? 3 : 2);
  }, []);

  const onTermine = useCallback((job: Job) => {
    setNiveau(job.niveau);
    setDetail(job.message);
    setEtape(4);
    setAtteinte(4);
  }, []);

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
      <StepBar courante={etape} atteinte={atteinte} onAller={aller} />
      {erreur && (
        <p className="mt-6 rounded-xl bg-brique/10 px-4 py-3 text-sm" role="alert">
          {erreur}
        </p>
      )}
      <div className="mt-8">
        <div hidden={etape !== 0}>
          <Depot
            session={session}
            profil={profil}
            lecture={lecture}
            onFichier={onFichier}
            onProfil={(id, suivant) => {
              setSession(id);
              setProfil(suivant);
              setJournal(null);
              setVersionProfil((v) => v + 1);
              invaliderGeneration(1);
            }}
            onContinuer={() => aller(1)}
          />
        </div>
        {atteinte >= 1 && session && profil && (
          <div hidden={etape !== 1}>
            <Nettoyage
              key={`${session}-${versionProfil}`}
              session={session}
              profil={profil}
              onResultat={onJournal}
              onContinuer={() => aller(2)}
            />
          </div>
        )}
        {atteinte >= 2 && session && (
          <div hidden={etape !== 2}>
            <Theme key={session} session={session} onTheme={onTheme} onContinuer={() => aller(3)} />
          </div>
        )}
        {atteinte >= 3 && session && (
          <div hidden={etape !== 3}>
            <Generation
              key={`${session}-${versionGeneration}`}
              session={session}
              pret={Boolean(journal && theme)}
              onTermine={onTermine}
            />
          </div>
        )}
        {etape === 4 && session && niveau && (
          <Telechargement session={session} niveau={niveau} detail={detail} />
        )}
      </div>
    </main>
  );
}
