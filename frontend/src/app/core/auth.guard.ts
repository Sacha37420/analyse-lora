import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { KeycloakService } from './keycloak.service';

export const authGuard: CanActivateFn = () => {
  const kc = inject(KeycloakService);
  if (kc.getToken()) return true;
  inject(Router).navigate(['/']);
  return false;
};

export const developerGuard: CanActivateFn = () => {
  const kc     = inject(KeycloakService);
  const router = inject(Router);
  if (kc.isDeveloper) return true;
  router.navigate(['/']);
  return false;
};
