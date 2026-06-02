import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService, Sensor } from '../../core/lora.service';
import { KeycloakService } from '../../core/keycloak.service';

@Component({
  selector: 'app-sensor-list',
  standalone: true,
  imports: [RouterLink, DatePipe, NavbarComponent],
  templateUrl: './sensor-list.html',
  styleUrl: './sensor-list.scss',
})
export class SensorListComponent implements OnInit {
  private lora = inject(LoraService);
  kc           = inject(KeycloakService);

  sensors  = signal<Sensor[]>([]);
  loading  = signal(true);
  error    = signal<string | null>(null);

  get isDeveloper(): boolean { return this.kc.isDeveloper; }

  ngOnInit(): void {
    this.lora.getSensors().subscribe({
      next:  s => { this.sensors.set(s); this.loading.set(false); },
      error: e => { this.error.set(`Erreur ${e.status ?? ''}`); this.loading.set(false); },
    });
  }
}
