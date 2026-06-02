import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService, Sensor, UserAccess } from '../../core/lora.service';

const PROTOCOLS = [
  { value: 'mqtt',       label: 'MQTT' },
  { value: 'http_push',  label: 'HTTP Push (Webhook)' },
  { value: 'http_poll',  label: 'HTTP Pull (Polling)' },
  { value: 'ttn',        label: 'The Things Network (TTN v3)' },
  { value: 'chirpstack', label: 'ChirpStack' },
  { value: 'helium',     label: 'Helium Network' },
];

@Component({
  selector: 'app-sensor-admin',
  standalone: true,
  imports: [RouterLink, FormsModule, NavbarComponent],
  templateUrl: './sensor-admin.html',
  styleUrl: './sensor-admin.scss',
})
export class SensorAdminComponent implements OnInit {
  private lora   = inject(LoraService);
  private route  = inject(ActivatedRoute);
  private router = inject(Router);

  protocols = PROTOCOLS;

  // Liste
  sensors = signal<Sensor[]>([]);
  loading = signal(true);

  // Formulaire création/édition
  editing      = signal<Sensor | null>(null);
  showForm     = signal(false);
  formName     = '';
  formSlug     = '';
  formDesc     = '';
  formProtocol = 'mqtt';
  formActive   = true;
  formError    = signal<string | null>(null);
  saving       = signal(false);

  // Gestion accès utilisateurs
  selectedSensor = signal<Sensor | null>(null);
  userAccesses   = signal<UserAccess[]>([]);
  newEmail       = '';
  usersError     = signal<string | null>(null);

  get editingId(): number | null {
    const id = this.route.snapshot.paramMap.get('id');
    return id ? Number(id) : null;
  }

  ngOnInit(): void {
    this.loadSensors();
  }

  loadSensors(): void {
    this.loading.set(true);
    this.lora.getSensors().subscribe({
      next: s => { this.sensors.set(s); this.loading.set(false); this.checkEditRoute(); },
      error: () => this.loading.set(false),
    });
  }

  private checkEditRoute(): void {
    const id = this.editingId;
    if (id) {
      const s = this.sensors().find(x => x.id === id);
      if (s) this.openEdit(s);
    }
  }

  openCreate(): void {
    this.editing.set(null);
    this.formName = '';
    this.formSlug = '';
    this.formDesc = '';
    this.formProtocol = 'mqtt';
    this.formActive = true;
    this.formError.set(null);
    this.showForm.set(true);
  }

  openEdit(s: Sensor): void {
    this.editing.set(s);
    this.formName     = s.name;
    this.formSlug     = s.slug;
    this.formDesc     = s.description;
    this.formProtocol = s.protocol;
    this.formActive   = s.is_active;
    this.formError.set(null);
    this.showForm.set(true);
    this.loadUsers(s);
  }

  saveForm(): void {
    this.saving.set(true);
    this.formError.set(null);
    const data = {
      name: this.formName,
      slug: this.formSlug,
      description: this.formDesc,
      protocol: this.formProtocol,
      is_active: this.formActive,
    };
    const obs = this.editing()
      ? this.lora.updateSensor(this.editing()!.id, data)
      : this.lora.createSensor(data);

    obs.subscribe({
      next: () => { this.saving.set(false); this.showForm.set(false); this.loadSensors(); },
      error: e => {
        this.saving.set(false);
        this.formError.set(e.error?.slug?.[0] ?? e.error?.name?.[0] ?? `Erreur ${e.status}`);
      },
    });
  }

  deleteSensor(s: Sensor): void {
    if (!confirm(`Supprimer "${s.name}" et toutes ses données ?`)) return;
    this.lora.deleteSensor(s.id).subscribe(() => this.loadSensors());
  }

  // Gestion des accès utilisateurs
  loadUsers(s: Sensor): void {
    this.selectedSensor.set(s);
    this.usersError.set(null);
    this.lora.getSensorUsers(s.id).subscribe({
      next: acc => this.userAccesses.set(acc),
      error: e  => this.usersError.set(`Erreur ${e.status}`),
    });
  }

  addUser(): void {
    const s = this.editing() ?? this.selectedSensor();
    if (!s || !this.newEmail.trim()) return;
    this.lora.addSensorUser(s.id, this.newEmail.trim().toLowerCase()).subscribe({
      next: () => { this.newEmail = ''; this.loadUsers(s); },
      error: e => this.usersError.set(`Erreur ${e.status}`),
    });
  }

  removeUser(email: string): void {
    const s = this.editing() ?? this.selectedSensor();
    if (!s) return;
    this.lora.removeSensorUser(s.id, email).subscribe(() => this.loadUsers(s));
  }

  autoSlug(): void {
    if (!this.formSlug) {
      this.formSlug = this.formName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    }
  }
}
