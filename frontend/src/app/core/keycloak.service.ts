import { Injectable } from '@angular/core';
import Keycloak from 'keycloak-js';
import { loginRedirectUri } from './redirect-uri';

interface EnvWindow {
  __env?: {
    keycloakUrl?:      string;
    keycloakRealm?:    string;
    keycloakClientId?: string;
    appUrl?:           string;
    apiUrl?:           string;
  };
}

@Injectable({ providedIn: 'root' })
export class KeycloakService {
  private kc!: Keycloak;

  async init(): Promise<boolean> {
    const env = (window as unknown as EnvWindow).__env ?? {};

    this.kc = new Keycloak({
      url:      env.keycloakUrl      ?? (window.location.protocol + '//' + window.location.hostname + ':8080'),
      realm:    env.keycloakRealm    ?? 'ssolab',
      clientId: env.keycloakClientId ?? 'analyse-lora',
    });

    // La page demandée, pas l'accueil : voir core/redirect-uri.ts.
    const redirectUri = loginRedirectUri(window.location.href, env.appUrl, window.location.origin);

    return this.kc.init({
      onLoad:           'login-required',
      checkLoginIframe: false,
      redirectUri,
      pkceMethod:       'S256',
    });
  }

  get username(): string {
    return (this.kc?.tokenParsed as Record<string, unknown>)?.['preferred_username'] as string ?? '';
  }

  get email(): string {
    return (this.kc?.tokenParsed as Record<string, unknown>)?.['email'] as string ?? '';
  }

  get groups(): string[] {
    return (this.kc?.tokenParsed as Record<string, unknown>)?.['groups'] as string[] ?? [];
  }

  get isDeveloper(): boolean {
    const g = this.groups;
    return g.includes('/developers') || g.includes('developers');
  }

  getToken(): string | undefined {
    return this.kc?.token;
  }

  isTokenExpired(minValidity = 0): boolean {
    return this.kc?.isTokenExpired(minValidity) ?? true;
  }

  async updateToken(minValidity: number): Promise<boolean> {
    try {
      return await this.kc.updateToken(minValidity);
    } catch {
      return false;
    }
  }

  logout(): void {
    // Retour sous le préfixe de l'app (<base href>, ex. /<app>/) : la racine du domaine
    // n'est pas une URI de retour du client depuis --prune-uris (LOGOUT_ERROR
    // invalid_redirect_uri, constaté sur peripheriques le 2026-11-08).
    this.kc.logout({ redirectUri: document.baseURI });
  }
}
