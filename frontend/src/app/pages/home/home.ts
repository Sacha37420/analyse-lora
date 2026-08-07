import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LoraService, DashboardGroup } from '../../core/lora.service';
import { KeycloakService } from '../../core/keycloak.service';
import { GroupPanelComponent } from './group-panel';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, GroupPanelComponent],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomeComponent implements OnInit {
  private lora = inject(LoraService);
  kc           = inject(KeycloakService);

  groups   = signal<DashboardGroup[]>([]);
  loading  = signal(true);
  error    = signal<string | null>(null);

  get username(): string    { return this.kc.username; }
  get isDeveloper(): boolean { return this.kc.isDeveloper; }

  ngOnInit(): void {
    this.lora.getDashboardGroups().subscribe({
      next:  g => { this.groups.set(g); this.loading.set(false); },
      error: e => { this.error.set(`Erreur (${e.status ?? 'réseau'})`); this.loading.set(false); },
    });
  }
}
