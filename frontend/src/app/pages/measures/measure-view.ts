import {
  Component, inject, OnInit, signal,
  ElementRef, ViewChild, AfterViewInit, OnDestroy,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NavbarComponent } from '../../shared/navbar/navbar';
import { LoraService, ComputedMeasure, MeasurePoint, Sensor } from '../../core/lora.service';
import { Chart, ChartData, ChartOptions, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-measure-view',
  standalone: true,
  imports: [RouterLink, FormsModule, NavbarComponent],
  templateUrl: './measure-view.html',
  styleUrl: './measure-view.scss',
})
export class MeasureViewComponent implements OnInit, OnDestroy {
  private lora  = inject(LoraService);
  private route = inject(ActivatedRoute);

  sensor   = signal<Sensor | null>(null);
  measures = signal<ComputedMeasure[]>([]);
  loading  = signal(true);
  error    = signal<string | null>(null);

  // Formulaire nouvelle grandeur
  showForm    = signal(false);
  editingId   = signal<number | null>(null);
  formName    = '';
  formFormula = '';
  formUnit    = '';
  formColor   = '#3b82f6';
  formDesc    = '';
  formError   = signal<string | null>(null);
  saving      = signal(false);

  // Plage temporelle
  startDate = this._defaultStart();
  endDate   = '';

  // Graphiques (Chart.js instances)
  private charts = new Map<number, Chart>();

  get sensorId(): number {
    return Number(this.route.snapshot.paramMap.get('id'));
  }

  ngOnInit(): void {
    this.lora.getSensor(this.sensorId).subscribe({ next: s => this.sensor.set(s) });
    this.loadMeasures();
  }

  ngOnDestroy(): void {
    this.charts.forEach(c => c.destroy());
  }

  loadMeasures(): void {
    this.loading.set(true);
    this.lora.getMeasures(this.sensorId).subscribe({
      next: m => {
        this.measures.set(m);
        this.loading.set(false);
        setTimeout(() => m.forEach(measure => this.computeAndDraw(measure)), 100);
      },
      error: e => { this.error.set(`Erreur ${e.status}`); this.loading.set(false); },
    });
  }

  computeAndDraw(measure: ComputedMeasure): void {
    this.lora.computeMeasure(measure.id, {
      start: this.startDate || undefined,
      end:   this.endDate   || undefined,
    }).subscribe({
      next: result => this.drawChart(measure, result.points),
    });
  }

  private drawChart(measure: ComputedMeasure, points: MeasurePoint[]): void {
    const canvas = document.getElementById(`chart-${measure.id}`) as HTMLCanvasElement | null;
    if (!canvas) return;

    const existing = this.charts.get(measure.id);
    if (existing) existing.destroy();

    const labels = points.map(p => new Date(p.t).toLocaleString('fr-FR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }));
    const values = points.map(p => p.v);

    const chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: `${measure.name}${measure.unit ? ' (' + measure.unit + ')' : ''}`,
          data: values,
          borderColor:     measure.color,
          backgroundColor: measure.color + '22',
          borderWidth: 2,
          pointRadius: points.length > 200 ? 0 : 3,
          fill: true,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        animation: false,
        scales: {
          x: {
            ticks: { maxTicksLimit: 10, maxRotation: 0 },
            grid: { color: '#e2e8f0' },
          },
          y: {
            title: { display: !!measure.unit, text: measure.unit, color: '#64748b', font: { size: 12 } },
            grid: { color: '#e2e8f0' },
          },
        },
        plugins: {
          legend: { display: true, position: 'top' },
          tooltip: { mode: 'index', intersect: false },
        },
      },
    });

    this.charts.set(measure.id, chart);
  }

  refreshAll(): void {
    this.measures().forEach(m => this.computeAndDraw(m));
  }

  // Formulaire
  openCreate(): void {
    this.editingId.set(null);
    this.formName = ''; this.formFormula = ''; this.formUnit = '';
    this.formColor = '#3b82f6'; this.formDesc = '';
    this.formError.set(null);
    this.showForm.set(true);
  }

  openEdit(m: ComputedMeasure): void {
    this.editingId.set(m.id);
    this.formName = m.name; this.formFormula = m.formula;
    this.formUnit = m.unit; this.formColor = m.color; this.formDesc = m.description;
    this.formError.set(null);
    this.showForm.set(true);
  }

  saveForm(): void {
    this.saving.set(true);
    this.formError.set(null);
    const data = {
      name: this.formName, formula: this.formFormula,
      unit: this.formUnit, color: this.formColor, description: this.formDesc,
    };
    const id = this.editingId();
    const obs = id
      ? this.lora.updateMeasure(id, data)
      : this.lora.createMeasure(this.sensorId, data);

    obs.subscribe({
      next: () => { this.saving.set(false); this.showForm.set(false); this.loadMeasures(); },
      error: e => {
        this.saving.set(false);
        this.formError.set(e.error?.formula?.[0] ?? e.error?.name?.[0] ?? `Erreur ${e.status}`);
      },
    });
  }

  deleteMeasure(m: ComputedMeasure): void {
    if (!confirm(`Supprimer "${m.name}" ?`)) return;
    this.lora.deleteMeasure(m.id).subscribe(() => this.loadMeasures());
  }

  private _defaultStart(): string {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().slice(0, 16);
  }

  formulaHint(): string {
    return `Exemples : row['temperature']   |   row['humidity'] / 100   |   row['voltage'] * 3.3`;
  }
}
