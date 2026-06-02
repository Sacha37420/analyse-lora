import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService, Sensor, SensorReading, ReadingsPage } from '../../core/lora.service';

@Component({
  selector: 'app-sensor-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, NavbarComponent],
  templateUrl: './sensor-detail.html',
  styleUrl: './sensor-detail.scss',
})
export class SensorDetailComponent implements OnInit {
  private lora  = inject(LoraService);
  private route = inject(ActivatedRoute);

  sensor   = signal<Sensor | null>(null);
  page     = signal<ReadingsPage | null>(null);
  loading  = signal(true);
  error    = signal<string | null>(null);

  startDate = '';
  endDate   = '';
  currentPage = 1;

  get sensorId(): number {
    return Number(this.route.snapshot.paramMap.get('id'));
  }

  get allColumns(): string[] {
    const readings = this.page()?.results ?? [];
    const keys = new Set<string>();
    readings.forEach(r => Object.keys(r.data).forEach(k => keys.add(k)));
    return ['timestamp', ...Array.from(keys)];
  }

  ngOnInit(): void {
    this.loadSensor();
    this.loadData();
  }

  private loadSensor(): void {
    this.lora.getSensor(this.sensorId).subscribe({
      next: s => this.sensor.set(s),
    });
  }

  loadData(page = 1): void {
    this.loading.set(true);
    this.currentPage = page;
    this.lora.getSensorData(this.sensorId, {
      start:     this.startDate  || undefined,
      end:       this.endDate    || undefined,
      page,
      page_size: 50,
    }).subscribe({
      next:  p => { this.page.set(p); this.loading.set(false); },
      error: e => { this.error.set(`Erreur ${e.status ?? ''}`); this.loading.set(false); },
    });
  }

  cellValue(reading: SensorReading, col: string): string {
    if (col === 'timestamp') {
      return new Date(reading.timestamp).toLocaleString('fr-FR');
    }
    const v = reading.data[col];
    return v != null ? String(v) : '—';
  }

  get totalPages(): number {
    const p = this.page();
    return p ? Math.ceil(p.count / p.page_size) : 1;
  }
}
