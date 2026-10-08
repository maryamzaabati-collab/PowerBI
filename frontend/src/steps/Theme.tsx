import { useState } from "react";
import { enregistrerTheme } from "../api";
import { ColorPickers } from "../components/ColorPickers";
import { ThemePreview } from "../components/ThemePreview";
import type { ThemeReponse } from "../types";

export function Theme({
  session,
  onTheme,
  onContinuer,
}: {
  session: string;
  onTheme: (theme: ThemeReponse) => void;
  onContinuer: () => void;
}) {
  const [couleurs, setCouleurs] = useState(["#0F6E56", "#E6A817", "#C4493A", "#1F4E79", "#6B4C9A"]);
  const [resultat, setResultat] = useState<ThemeReponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function enregistrer(palette = couleurs) {
    setMessage(null);
    try {
      const reponse = await enregistrerTheme(session, palette);
      setResultat(reponse);
      onTheme(reponse);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Thème refusé.");
    }
  }

  const fond = resultat?.contraste_texte.background ?? "#FFFFFF";
  const encre = resultat?.contraste_texte.foreground ?? "#1A1A1A";

  return (
    <section className="space-y-6">
      <ColorPickers
        couleurs={couleurs}
        onChange={(palette) => {
          setCouleurs(palette);
          setResultat(null);
        }}
      />
      <ThemePreview couleurs={couleurs} fond={fond} encre={encre} />
      {resultat && (
        <ul className="space-y-2 text-sm">
          <li>
            Contraste du texte : {resultat.contraste_texte.ratio} (seuil 4,5). Encre {resultat.contraste_texte.foreground}, fond{" "}
            {resultat.contraste_texte.background}.
          </li>
          {resultat.contrastes.map((item) => (
            <li key={item.couleur}>
              {item.couleur} sur le fond : {item.ratio} {item.suffisant ? "(au-dessus de 3)." : `(sous le seuil de 3).`}
              {!item.suffisant && item.proposition && (
                <>
                  {" "}
                  Proposition : {item.proposition}.{" "}
                  <button
                    type="button"
                    className="text-pin"
                    onClick={() => {
                      const suite = couleurs.map((couleur) => (couleur.toUpperCase() === item.couleur ? item.proposition! : couleur));
                      setCouleurs(suite);
                      void enregistrer(suite);
                    }}
                  >
                    L'utiliser
                  </button>
                  . Vous pouvez garder la vôtre.
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {message && <p className="rounded-xl bg-brique/10 px-4 py-3 text-sm">{message}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="button" className="rounded-full bg-pin px-5 py-2 text-sm font-semibold text-white" onClick={() => enregistrer()}>
          Enregistrer le thème
        </button>
        {resultat && (
          <button type="button" className="rounded-full bg-encre px-5 py-2 text-sm font-semibold text-papier" onClick={onContinuer}>
            Passer à la génération
          </button>
        )}
      </div>
    </section>
  );
}
