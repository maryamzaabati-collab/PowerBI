import { useState } from "react";

export function DropZone({
  occupé,
  onFichier,
}: {
  occupé: boolean;
  onFichier: (fichier: File) => void;
}) {
  const [survole, setSurvole] = useState(false);

  return (
    <label
      className={`block cursor-pointer rounded-2xl border-2 border-dashed px-6 py-12 text-center ${
        survole ? "border-pin bg-pin/5" : "border-filet bg-carte"
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        setSurvole(true);
      }}
      onDragLeave={() => setSurvole(false)}
      onDrop={(event) => {
        event.preventDefault();
        setSurvole(false);
        const fichier = event.dataTransfer.files?.[0];
        if (fichier) onFichier(fichier);
      }}
    >
      <input
        type="file"
        accept=".csv,text/csv"
        className="sr-only"
        disabled={occupé}
        onChange={(event) => {
          const fichier = event.target.files?.[0];
          if (fichier) onFichier(fichier);
        }}
      />
      <p className="font-serif text-2xl text-encre">Déposez un CSV</p>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-encre/70">
        Fichier .csv uniquement, 50 Mo, 200 000 lignes et 80 colonnes au plus. L'encodage et le
        séparateur sont proposés, vous pouvez les corriger. Rien ne quitte cette machine.
      </p>
      <span className="mt-6 inline-block rounded-full bg-pin px-4 py-2 text-sm font-semibold text-white">
        {occupé ? "Lecture en cours…" : "Parcourir"}
      </span>
    </label>
  );
}
