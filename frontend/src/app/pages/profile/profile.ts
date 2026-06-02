import { Component, inject, OnInit, signal } from '@angular/core';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService } from '../../core/lora.service';
import { KeycloakService } from '../../core/keycloak.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [NavbarComponent],
  templateUrl: './profile.html',
  styleUrl: './profile.scss',
})
export class ProfileComponent implements OnInit {
  private lora = inject(LoraService);
  kc           = inject(KeycloakService);

  me      = signal<any>(null);
  loading = signal(true);
  error   = signal<string | null>(null);

  ngOnInit(): void {
    this.lora.getMe().subscribe({
      next: m => { this.me.set(m); this.loading.set(false); },
      error: e => { this.error.set(`Erreur ${e.status ?? 'réseau'}`); this.loading.set(false); },
    });
  }
}
