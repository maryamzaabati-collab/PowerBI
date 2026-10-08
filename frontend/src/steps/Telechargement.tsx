import { urlTelechargement } from "../api";

export function Telechargement({ session, niveau, detail }: { session: string; niveau: string; detail: string | null }) {
  return (
    <section className="space-y-4">
      <p className="rounded-xl bg-pin/10 px-4 py-3 text-sm">
        Niveau obtenu : <strong>{niveau}</strong>. {detail}
      </p>
      <a
        className="inline-block rounded-full bg-pin px-5 py-2 text-sm font-semibold text-white"
        href={urlTelechargement(session)}
      >
        Télécharger le ZIP
      </a>
      <ul className="list-disc space-y-2 pl-5 text-sm leading-6">
        <li>Ouvrez Rapport.pbip avec Power BI Desktop grand public, pas l'édition Report Server.</li>
        <li>Renseignez CheminFichierCsv avec le chemin absolu de donnees-nettoyees.csv, puis actualisez.</li>
        <li>Si les couleurs manquent : Affichage → Thèmes → Parcourir, theme.json.</li>
        <li>Aux niveaux B et C, posez les visuels indiqués dans LISEZMOI.txt. Les mesures sont déjà là.</li>
      </ul>
    </section>
  );
}
