/**
 * Champs `<input type="datetime-local">` : leur valeur est une heure locale
 * sans fuseau (`2026-07-14T10:00`). Envoyée telle quelle, l'API l'interprète
 * dans le fuseau du serveur, pas dans celui de l'utilisateur : on envoie
 * donc l'instant exact, en ISO UTC.
 */
export function localInputToIso(value: string): string | undefined {
  if (!value) return undefined;
  const d = new Date(value);   // sans décalage : lu en heure locale du navigateur
  return isNaN(d.getTime()) ? undefined : d.toISOString();
}

/** Instant → valeur d'un `<input type="datetime-local">`, en heure locale. */
export function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
