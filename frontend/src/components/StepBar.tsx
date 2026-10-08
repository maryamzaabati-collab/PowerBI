const ETAPES = ["Dépôt", "Nettoyage", "Thème", "Génération", "Téléchargement"] as const;

export function StepBar({ courante }: { courante: number }) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {ETAPES.map((nom, index) => {
        const etat = index < courante ? "faite" : index === courante ? "active" : "future";
        return (
          <li
            key={nom}
            className={
              etat === "active"
                ? "rounded-full bg-pin px-3 py-2 text-center text-sm font-semibold text-white"
                : etat === "faite"
                  ? "rounded-full bg-pin/15 px-3 py-2 text-center text-sm font-medium text-pin"
                  : "rounded-full bg-filet px-3 py-2 text-center text-sm text-encre/40"
            }
            aria-current={etat === "active" ? "step" : undefined}
          >
            {index + 1}. {nom}
          </li>
        );
      })}
    </ol>
  );
}
