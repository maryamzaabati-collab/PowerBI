const PRESETS: { nom: string; couleurs: string[] }[] = [
  { nom: "Forêt", couleurs: ["#0F6E56", "#E6A817", "#C4493A", "#1F4E79", "#6B4C9A"] },
  { nom: "Encre", couleurs: ["#1F4E79", "#3D6B99", "#C4493A", "#E6A817", "#6B4C9A"] },
  { nom: "Ardoise", couleurs: ["#334155", "#0F766E", "#B45309", "#9F1239", "#4338CA"] },
  { nom: "Sable", couleurs: ["#9A3412", "#B45309", "#A16207", "#3F6212", "#1E3A5F"] },
];

export function ColorPickers({
  couleurs,
  onChange,
}: {
  couleurs: string[];
  onChange: (couleurs: string[]) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((palette) => (
          <button
            key={palette.nom}
            type="button"
            className="rounded-full border border-filet bg-carte px-3 py-1 text-sm"
            onClick={() => onChange(palette.couleurs)}
          >
            {palette.nom}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-4">
        {couleurs.map((couleur, index) => (
          <label key={index} className="flex items-center gap-2 text-sm">
            <input
              type="color"
              value={couleur}
              aria-label={`Couleur ${index + 1}`}
              onChange={(event) => {
                const suite = [...couleurs];
                suite[index] = event.target.value.toUpperCase();
                onChange(suite);
              }}
            />
            <span className="font-mono">{couleur}</span>
            {couleurs.length > 3 && (
              <button
                type="button"
                className="text-brique"
                onClick={() => onChange(couleurs.filter((_, i) => i !== index))}
              >
                Retirer
              </button>
            )}
          </label>
        ))}
        {couleurs.length < 5 && (
          <button
            type="button"
            className="rounded-full border border-filet px-3 py-1 text-sm"
            onClick={() => onChange([...couleurs, "#1F4E79"])}
          >
            Ajouter une pastille
          </button>
        )}
      </div>
      <p className="text-xs text-encre/60">Trois à cinq couleurs. Power BI dérive la suite de la palette.</p>
    </div>
  );
}
