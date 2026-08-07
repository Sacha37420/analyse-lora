import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { LoraService, ConnectionInfo, ConnectionMethod, Webhook } from '../../core/lora.service';

@Component({
  selector: 'app-sensor-connection',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './sensor-connection.html',
  styleUrl: './sensor-connection.scss',
})
export class SensorConnectionComponent implements OnInit {
  private lora  = inject(LoraService);
  private route = inject(ActivatedRoute);

  info      = signal<ConnectionInfo | null>(null);
  methods   = signal<ConnectionMethod[]>([]);
  webhooks  = signal<Webhook[]>([]);
  loading   = signal(true);
  saving    = signal(false);
  error     = signal<string | null>(null);
  saveOk    = signal(false);

  activeMethodTab   = signal('');
  selectedWebhookId = signal<number | null>(null);

  get sensorId(): number {
    return Number(this.route.snapshot.paramMap.get('id'));
  }

  get apiUrl(): string {
    const env = (window as any).__env;
    return env?.apiUrl ?? 'http://localhost:8086';
  }

  get webhooksForProtocol(): Webhook[] {
    return this.webhooks().filter(w => w.protocol === this.activeMethodTab());
  }

  get selectedWebhook(): Webhook | undefined {
    const id = this.selectedWebhookId();
    return id ? this.webhooks().find(w => w.id === id) : undefined;
  }

  ngOnInit(): void {
    this.lora.getConnectionMethods().subscribe({ next: m => this.methods.set(m) });
    this.lora.getWebhooks().subscribe({ next: w => this.webhooks.set(w) });
    this.lora.getConnectionInfo(this.sensorId).subscribe({
      next: info => {
        this.info.set(info);
        this.activeMethodTab.set(info.protocol);
        this.selectedWebhookId.set(info.webhook?.id ?? null);
        this.loading.set(false);
      },
      error: e => { this.error.set(`Erreur ${e.status}`); this.loading.set(false); },
    });
  }

  fieldValue(key: string): string {
    return this.info()?.connection_config?.[key] ?? '';
  }

  setField(key: string, value: string): void {
    const info = this.info();
    if (!info) return;
    info.connection_config = { ...info.connection_config, [key]: value };
    this.info.set({ ...info });
  }

  save(): void {
    const info = this.info();
    if (!info) return;
    this.saving.set(true);
    this.saveOk.set(false);
    this.lora.updateConnectionConfig(this.sensorId, {
      protocol:          info.protocol,
      connection_config: info.connection_config,
      webhook:           this.selectedWebhookId(),
    }).subscribe({
      next: () => { this.saving.set(false); this.saveOk.set(true); },
      error: e => { this.saving.set(false); this.error.set(`Erreur ${e.status}`); },
    });
  }

  selectWebhook(id: string): void {
    this.selectedWebhookId.set(id ? Number(id) : null);
    const info = this.info();
    if (info) this.info.set({ ...info, connection_config: {} });
  }

  interpolate(step: string): string {
    const info = this.info();
    if (!info) return step;
    return step
      .replace(/\{api_url\}/g,   this.apiUrl)
      .replace(/\{slug\}/g,       info.slug)
      .replace(/\{api_key\}/g,    info.api_key)
      .replace(/\{api_ingest_url\}/g, `${this.apiUrl}${info.api_ingest_url}`)
      .replace(/\{([^}]+)\}/g,   (_, k) => info.connection_config?.[k] ?? `{${k}}`);
  }

  selectMethod(protocol: string): void {
    this.activeMethodTab.set(protocol);
    this.selectedWebhookId.set(null);
    const info = this.info();
    if (info) {
      this.info.set({ ...info, protocol, connection_config: {} });
    }
  }

  get activeMethod(): ConnectionMethod | undefined {
    return this.methods().find(m => m.protocol === this.activeMethodTab());
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text);
  }
}
