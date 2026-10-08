export type Role =
  | "temporel"
  | "numerique"
  | "booleen"
  | "geographique"
  | "identifiant"
  | "categorie"
  | "texte"
  | "ignoree";

export type Regles = {
  doublons: boolean;
  trim: boolean;
  vides: boolean;
  casse: boolean;
  nombres: boolean;
  dates: boolean;
};

export type ColonneProfil = {
  nom: string;
  nom_source: string;
  role_propose: Role;
  role_libelle: string;
  type_propose: string;
  manquants: number;
  cardinalite: number;
  ratio_cardinalite: number;
  part_doublons: number;
  date_ambigue: boolean;
  aberrantes: { compte: number; exemples: number[] } | null;
};

export type Apercu = { colonnes: string[]; lignes: string[][] };

export type Profil = {
  nom_fichier: string;
  lignes: number;
  colonnes_nombre: number;
  doublons_exacts: number;
  encodage: string;
  separateur: string;
  separateur_libelle: string;
  decimal: string;
  avertissement_entete: string | null;
  colonnes: ColonneProfil[];
  apercu: Apercu;
};

export type Journal = {
  lignes_avant: number;
  lignes_apres: number;
  regles: { id: string; libelle: string; active: boolean; lignes_avant: number; lignes_apres: number }[];
  colonnes: {
    nom: string;
    role: Role;
    type_avant: string;
    type_apres: string;
    cellules_modifiees: number;
    manquants_avant: number;
    manquants_apres: number;
    date_ambigue: boolean;
  }[];
  dates_ambigues: string[];
  date_pilote: string | null;
};

export type Contraste = {
  couleur: string;
  ratio: number;
  seuil: number;
  suffisant: boolean;
  proposition: string | null;
};

export type ThemeReponse = {
  theme: { dataColors: string[]; background: string; foreground: string };
  contrastes: Contraste[];
  contraste_texte: { foreground: string; background: string; ratio: number };
};

export type Job = {
  job: string;
  etat: "en_cours" | "termine" | "erreur";
  etape: string;
  libelle: string;
  progression: number;
  niveau: string | null;
  message: string | null;
  erreur: string | null;
};

export const ROLES: { id: Role; libelle: string }[] = [
  { id: "temporel", libelle: "Temporel" },
  { id: "numerique", libelle: "Numérique" },
  { id: "booleen", libelle: "Booléen" },
  { id: "geographique", libelle: "Géographique" },
  { id: "identifiant", libelle: "Identifiant" },
  { id: "categorie", libelle: "Catégorie" },
  { id: "texte", libelle: "Texte libre" },
  { id: "ignoree", libelle: "Ignorée" },
];

export const REGLES_DEFAUT: Regles = {
  doublons: true,
  trim: true,
  vides: true,
  casse: false,
  nombres: true,
  dates: true,
};
