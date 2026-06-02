import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService, Sensor } from '../../core/lora.service';
import { KeycloakService } from '../../core/keycloak.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, DatePipe, NavbarComponent],
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomeComponent implements OnInit {
  private lora = inject(LoraService);
  kc           = inject(KeycloakService);

  sensors  = signal<Sensor[]>([]);
  loading  = signal(true);
  error    = signal<string | null>(null);

  get username(): string    { return this.kc.username; }
  get isDeveloper(): boolean { return this.kc.isDeveloper; }

  ngOnInit(): void {
    this.lora.getSensors().subscribe({
      next:  s => { this.sensors.set(s); this.loading.set(false); },
      error: e => { this.error.set(`Erreur (${e.status ?? 'réseau'})`); this.loading.set(false); },
    });
  }

  dataKeys(sensor: Sensor): string[] {
    const data = sensor.last_reading?.data;
    return data ? Object.keys(data) : [];
  }

  dataValue(sensor: Sensor, key: string): string {
    const v = sensor.last_reading?.data?.[key];
    return v != null ? String(v) : '—';
  }
}
