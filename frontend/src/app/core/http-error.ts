import { HttpErrorResponse } from '@angular/common/http';

/**
 * Message lisible pour une erreur HTTP : ce qui s'est passé et quoi faire,
 * jamais un code seul (« Erreur 403 ») ni le corps brut de la réponse.
 * `action` décrit ce qui a échoué : « Chargement des capteurs impossible ».
 */
export function messageErreur(e: HttpErrorResponse | { status?: number }, action: string): string {
  const status = e?.status ?? 0;
  if (status === 0)   return `${action} : serveur injoignable. Vérifiez votre connexion puis réessayez.`;
  if (status === 401) return `${action} : votre session a expiré. Rechargez la page pour vous reconnecter.`;
  if (status === 403) return `${action} : votre compte n'a pas accès à cet élément.`;
  if (status === 404) return `${action} : élément introuvable (il a peut-être été supprimé).`;
  if (status >= 500)  return `${action} : erreur du serveur. Réessayez dans quelques minutes.`;
  return `${action} : la demande a été refusée. Vérifiez la saisie puis réessayez.`;
}
