import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { LoraService, Webhook, ConnectionMethod, UserAccess } from '../../core/lora.service';

@Component({
  selector: 'app-webhook-admin',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './webhook-admin.html',
  styleUrl: './webhook-admin.scss',
})
export class WebhookAdminComponent implements OnInit {
  private lora  = inject(LoraService);
  private route = inject(ActivatedRoute);

  // Liste
  webhooks = signal<Webhook[]>([]);
  methods  = signal<ConnectionMethod[]>([]);
  loading  = signal(true);

  // Formulaire création/édition
  editing      = signal<Webhook | null>(null);
  showForm     = signal(false);
  formName     = '';
  formProtocol = '';
  formConfig: Record<string, string> = {};
  formActive   = true;
  formError    = signal<string | null>(null);
  saving       = signal(false);

  // Gestion des accès utilisateurs
  userAccesses = signal<UserAccess[]>([]);
  newEmail     = '';
  usersError   = signal<string | null>(null);

  get editingId(): number | null {
    const id = this.route.snapshot.paramMap.get('id');
    return id ? Number(id) : null;
  }

  get webhookProtocols(): ConnectionMethod[] {
    return this.methods().filter(m => m.supports_webhook);
  }

  get activeMethod(): ConnectionMethod | undefined {
    return this.methods().find(m => m.protocol === this.formProtocol);
  }

  get apiUrl(): string {
    const env = (window as any).__env;
    return env?.apiUrl ?? 'http://localhost:8086';
  }

  ngOnInit(): void {
    this.lora.getConnectionMethods().subscribe({ next: m => this.methods.set(m) });
    this.loadWebhooks();
  }

  loadWebhooks(): void {
    this.loading.set(true);
    this.lora.getWebhooks().subscribe({
      next: w => { this.webhooks.set(w); this.loading.set(false); this.checkEditRoute(); },
      error: () => this.loading.set(false),
    });
  }

  private checkEditRoute(): void {
    const id = this.editingId;
    if (id) {
      const w = this.webhooks().find(x => x.id === id);
      if (w) this.openEdit(w);
    }
  }

  openCreate(): void {
    this.editing.set(null);
    this.formName     = '';
    this.formProtocol = this.webhookProtocols[0]?.protocol ?? '';
    this.formConfig   = {};
    this.formActive   = true;
    this.formError.set(null);
    this.showForm.set(true);
  }

  openEdit(w: Webhook): void {
    this.editing.set(w);
    this.formName     = w.name;
    this.formProtocol = w.protocol;
    this.formConfig   = { ...w.connection_config };
    this.formActive   = w.is_active;
    this.formError.set(null);
    this.showForm.set(true);
    this.loadUsers(w);
  }

  // Gestion des accès utilisateurs — partager ce webhook donne accès à tous
  // les capteurs qui y sont rattachés, présents et futurs.
  loadUsers(w: Webhook): void {
    this.usersError.set(null);
    this.lora.getWebhookUsers(w.id).subscribe({
      next: acc => this.userAccesses.set(acc),
      error: e  => this.usersError.set(`Erreur ${e.status}`),
    });
  }

  addUser(): void {
    const w = this.editing();
    if (!w || !this.newEmail.trim()) return;
    this.lora.addWebhookUser(w.id, this.newEmail.trim().toLowerCase()).subscribe({
      next: () => { this.newEmail = ''; this.loadUsers(w); },
      error: e => this.usersError.set(`Erreur ${e.status}`),
    });
  }

  removeUser(email: string): void {
    const w = this.editing();
    if (!w) return;
    this.lora.removeWebhookUser(w.id, email).subscribe(() => this.loadUsers(w));
  }

  onProtocolChange(): void {
    if (!this.editing()) this.formConfig = {};
  }

  fieldValue(key: string): string {
    return this.formConfig[key] ?? '';
  }

  setField(key: string, value: string): void {
    this.formConfig = { ...this.formConfig, [key]: value };
  }

  saveForm(): void {
    this.saving.set(true);
    this.formError.set(null);
    const data = {
      name: this.formName,
      protocol: this.formProtocol,
      connection_config: this.formConfig,
      is_active: this.formActive,
    };
    const obs = this.editing()
      ? this.lora.updateWebhook(this.editing()!.id, data)
      : this.lora.createWebhook(data);

    obs.subscribe({
      next: () => { this.saving.set(false); this.showForm.set(false); this.loadWebhooks(); },
      error: e => {
        this.saving.set(false);
        this.formError.set(e.error?.name?.[0] ?? `Erreur ${e.status}`);
      },
    });
  }

  deleteWebhook(w: Webhook): void {
    const count = w.sensor_count;
    const warn = count > 0
      ? ` ${count} capteur(s) rattaché(s) perdront leur configuration réseau partagée (app_id/region/clé) et devront être reconfigurés.`
      : '';
    if (!confirm(`Supprimer le webhook "${w.name}" ?${warn}`)) return;
    this.lora.deleteWebhook(w.id).subscribe(() => this.loadWebhooks());
  }

  ingestUrl(w: Webhook): string {
    return `${this.apiUrl}/api/webhooks/${w.id}/data/`;
  }

  interpolate(step: string, w: Webhook): string {
    return step
      .replace(/\{api_ingest_url\}/g, this.ingestUrl(w))
      .replace(/\{api_key\}/g, w.api_key)
      .replace(/\{([^}]+)\}/g, (_, k) => w.connection_config?.[k] ?? `{${k}}`);
  }

  copyToClipboard(text: string): void {
    navigator.clipboard.writeText(text);
  }
}
