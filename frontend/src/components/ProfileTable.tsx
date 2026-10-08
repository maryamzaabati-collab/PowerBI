import type { Apercu, ColonneProfil } from "../types";

function pct(valeur: number) {
  return `${Math.round(valeur * 1000) / 10} %`;
}

export function ProfileTable({ colonnes, apercu }: { colonnes: ColonneProfil[]; apercu: Apercu }) {
  return (
    <div className="space-y-6">
      <div className="overflow-x-auto rounded-xl border border-filet">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-pin/10 text-encre">
            <tr>
              {["Colonne", "Rôle proposé", "Manquants", "Distincts", "Doublons", "Signal"].map((titre) => (
                <th key={titre} className="px-3 py-2 font-semibold">
                  {titre}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {colonnes.map((col) => (
              <tr key={col.nom} className="border-t border-filet">
                <td className="px-3 py-2">
                  <div className="font-medium">{col.nom}</div>
                  {col.nom_source !== col.nom && (
                    <div className="text-xs text-encre/60">source : {col.nom_source}</div>
                  )}
                </td>
                <td className="px-3 py-2">{col.role_libelle}</td>
                <td className="px-3 py-2">{pct(col.manquants)}</td>
                <td className="px-3 py-2">{col.cardinalite}</td>
                <td className="px-3 py-2">{pct(col.part_doublons)}</td>
                <td className="px-3 py-2 text-xs">
                  {col.date_ambigue && "Date ambiguë. "}
                  {col.aberrantes && col.aberrantes.compte > 0 && `${col.aberrantes.compte} aberrantes.`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-xl border border-filet">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-carte">
            <tr>
              {apercu.colonnes.map((col) => (
                <th key={col} className="px-2 py-2 font-semibold">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {apercu.lignes.map((ligne, index) => (
              <tr key={index} className="border-t border-filet">
                {ligne.map((cellule, numero) => (
                  <td key={numero} className="max-w-[16rem] truncate px-2 py-1">
                    {cellule}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-encre/60">Aperçu des 50 premières lignes, cellules tronquées à 200 caractères.</p>
    </div>
  );
}
