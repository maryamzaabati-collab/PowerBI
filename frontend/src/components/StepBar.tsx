const ETAPES = ["Dépôt", "Nettoyage", "Thème", "Génération", "Téléchargement"] as const;

const CLASSES = {
  active: "rounded-full bg-pin px-3 py-2 text-center text-sm font-semibold text-white",
  faite: "rounded-full bg-pin/15 px-3 py-2 text-center text-sm font-medium text-pin",
  future: "rounded-full bg-filet px-3 py-2 text-center text-sm text-encre/40",
} as const;

export function StepBar({
  courante,
  atteinte = courante,
  onAller,
}: {
  courante: number;
  atteinte?: number;
  onAller?: (index: number) => void;
}) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {ETAPES.map((nom, index) => {
        const etat = index === courante ? "active" : index <= atteinte ? "faite" : "future";
        const cliquable = Boolean(onAller) && etat === "faite";
        return (
          <li key={nom} aria-current={etat === "active" ? "step" : undefined}>
            {cliquable ? (
              <button
                type="button"
                className={`${CLASSES.faite} w-full transition hover:bg-pin/25 focus:outline-none focus-visible:ring-2 focus-visible:ring-pin`}
                onClick={() => onAller?.(index)}
              >
                {index + 1}. {nom}
              </button>
            ) : (
              <div className={CLASSES[etat]}>
                {index + 1}. {nom}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
