import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { KeycloakService } from '../../core/keycloak.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './navbar.html',
  styleUrl: './navbar.scss',
})
export class NavbarComponent {
  kc = inject(KeycloakService);

  get username(): string    { return this.kc.username; }
  get isDeveloper(): boolean { return this.kc.isDeveloper; }

  logout(): void { this.kc.logout(); }
}
