import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { LoraService } from '../../core/lora.service';

interface WeatherScope {
  type: 'webhook' | 'sensor';
  id: number;
  name: string;
  weatherApiKey: string;
  weatherLocation: string;
}

@Component({
  selector: 'app-weather-settings',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './weather-settings.html',
  styleUrl: './weather-settings.scss',
})
export class WeatherSettingsComponent implements OnInit {
  private lora = inject(LoraService);

  scopes  = signal<WeatherScope[]>([]);
  loading = signal(true);
  error   = signal<string | null>(null);
  savingKey = signal<string | null>(null);
  savedKey  = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin([this.lora.getWebhooks(), this.lora.getSensors()]).subscribe({
      next: ([webhooks, sensors]) => {
        const webhookScopes: WeatherScope[] = webhooks.map(w => ({
          type: 'webhook',
          id: w.id,
          name: w.name,
          weatherApiKey: w.weather_api_key ?? '',
          weatherLocation: w.weather_location ?? '',
        }));
        const sensorScopes: WeatherScope[] = sensors
          .filter(s => !s.webhook)
          .map(s => ({
            type: 'sensor',
            id: s.id,
            name: s.name,
            weatherApiKey: s.weather_api_key ?? '',
            weatherLocation: s.weather_location ?? '',
          }));
        this.scopes.set([...webhookScopes, ...sensorScopes]);
        this.loading.set(false);
      },
      error: e => { this.error.set(`Erreur ${e.status}`); this.loading.set(false); },
    });
  }

  scopeKey(s: WeatherScope): string {
    return `${s.type}-${s.id}`;
  }

  isConfigured(s: WeatherScope): boolean {
    return !!s.weatherApiKey && !!s.weatherLocation;
  }

  save(scope: WeatherScope): void {
    const key = this.scopeKey(scope);
    this.savingKey.set(key);
    this.savedKey.set(null);
    const data = { weather_api_key: scope.weatherApiKey, weather_location: scope.weatherLocation };

    const onSuccess = (): void => { this.savingKey.set(null); this.savedKey.set(key); };
    const onError = (e: { status?: number }): void => {
      this.savingKey.set(null);
      this.error.set(`Erreur ${e.status}`);
    };

    if (scope.type === 'webhook') {
      this.lora.updateWebhookWeather(scope.id, data).subscribe({ next: onSuccess, error: onError });
    } else {
      this.lora.updateSensorWeather(scope.id, data).subscribe({ next: onSuccess, error: onError });
    }
  }
}
