export function ThemePreview({
  couleurs,
  fond,
  encre,
}: {
  couleurs: string[];
  fond: string;
  encre: string;
}) {
  const [a, b, c] = [couleurs[0], couleurs[1] ?? couleurs[0], couleurs[2] ?? couleurs[0]];
  return (
    <figure className="rounded-2xl border border-filet p-4" style={{ background: fond, color: encre }}>
      <figcaption className="mb-3 text-xs uppercase tracking-wide opacity-70">
        Aperçu navigateur, pas le rendu Power BI
      </figcaption>
      <svg viewBox="0 0 640 220" className="w-full" role="img" aria-label="Aperçu indicatif du thème">
        <rect x="0" y="0" width="140" height="70" rx="8" fill={a} />
        <rect x="152" y="0" width="140" height="70" rx="8" fill={b} />
        <rect x="304" y="0" width="140" height="70" rx="8" fill={c} />
        <text x="16" y="42" fill={fond} fontFamily="Segoe UI, sans-serif" fontSize="16">
          Carte
        </text>
        {[40, 70, 50, 90, 60].map((h, i) => (
          <rect key={i} x={20 + i * 36} y={180 - h} width="24" height={h} fill={couleurs[i % couleurs.length]} />
        ))}
        <polyline
          fill="none"
          stroke={a}
          strokeWidth="3"
          points="250,170 290,140 330,150 370,110 410,120 450,90"
        />
        <rect x="480" y="100" width="140" height="28" fill={a} />
        <text x="492" y="119" fill={fond} fontFamily="Segoe UI, sans-serif" fontSize="12">
          En-tête
        </text>
        <rect x="480" y="128" width="140" height="22" fill={encre} opacity="0.08" />
        <rect x="480" y="150" width="140" height="22" fill={encre} opacity="0.04" />
      </svg>
    </figure>
  );
}
