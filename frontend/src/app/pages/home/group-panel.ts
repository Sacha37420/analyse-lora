import {
  Component, Input, OnInit, OnDestroy,
  ElementRef, ViewChild, inject, signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import * as Plotly from 'plotly.js-basic-dist-min';
import { LoraService, DashboardGroup, DashboardChartResult, GaugeData, Period } from '../../core/lora.service';
import { GaugeComponent } from '../../shared/gauge/gauge';

const PERIODS: { value: Period; label: string }[] = [
  { value: 'day',   label: 'Jour' },
  { value: 'week',  label: 'Semaine' },
  { value: 'month', label: 'Mois' },
];

// Slots de la palette catégorielle --series-N (voir styles.scss) à exclure du
// graphique : 3 (aqua, trop proche du vert) 6 (vert) et 8 (rouge) sont déjà le
// vocabulaire réservé du delta intérieur/extérieur des jauges — les réutiliser
// pour une simple identité de capteur créerait une confusion de sens. Ordre
// choisi et revalidé (CVD + normal-vision, paires adjacentes) avec le script
// de la skill dataviz : bleu, magenta, jaune, violet, orange.
const CHART_SAFE_SERIES_SLOTS = [1, 5, 4, 7, 2];

@Component({
  selector: 'app-group-panel',
  standalone: true,
  imports: [FormsModule, GaugeComponent],
  templateUrl: './group-panel.html',
  styleUrl: './group-panel.scss',
})
export class GroupPanelComponent implements OnInit, OnDestroy {
  @Input({ required: true }) group!: DashboardGroup;

  private lora = inject(LoraService);
  private plotted = false;
  private sensorColorMap = new Map<number, string>();

  @ViewChild('plotDiv') private plotRef?: ElementRef<HTMLDivElement>;

  periods       = PERIODS;
  fields        = signal<string[]>([]);
  selectedField = signal('');
  period        = signal<Period>('day');
  gauges        = signal<GaugeData[]>([]);
  loading       = signal(true);
  chartLoading  = signal(false);
  error         = signal<string | null>(null);

  get isTemperature(): boolean {
    return this.selectedField().toLowerCase().includes('temp');
  }

  get unit(): string {
    return this.isTemperature ? '°C' : '';
  }

  get hasGauges(): boolean {
    return this.group.sensors.length > 0;
  }

  ngOnInit(): void {
    this.buildSensorColorMap();
    this.lora.getDashboardFields(this.group.type, this.group.id).subscribe({
      next: fields => {
        this.fields.set(fields);
        this.selectedField.set(fields.includes('TempC_SHT') ? 'TempC_SHT' : (fields[0] ?? ''));
        this.loading.set(false);
        if (fields.length) this.refresh();
      },
      error: e => { this.error.set(`Erreur ${e.status}`); this.loading.set(false); },
    });
  }

  ngOnDestroy(): void {
    if (this.plotted && this.plotRef?.nativeElement) {
      Plotly.purge(this.plotRef.nativeElement);
    }
  }

  onFieldChange(): void { this.refresh(); }
  onPeriodChange(): void { this.refresh(); }

  /** Une couleur par capteur, stable et partagée entre la ligne du graphique et le
   *  remplissage de sa jauge — voir CHART_SAFE_SERIES_SLOTS. */
  private buildSensorColorMap(): void {
    const rootStyle = getComputedStyle(document.documentElement);
    const colors = CHART_SAFE_SERIES_SLOTS.map(i => rootStyle.getPropertyValue(`--series-${i}`).trim());
    this.group.sensors.forEach((s, i) => {
      this.sensorColorMap.set(s.id, colors[i % colors.length]);
    });
  }

  colorForSensor(sensorId: number): string {
    return this.sensorColorMap.get(sensorId) ?? 'var(--accent)';
  }

  refresh(): void {
    const field = this.selectedField();
    if (!field) return;

    this.chartLoading.set(true);
    this.lora.getDashboardChart(this.group.type, this.group.id, field, this.period()).subscribe({
      next: data => {
        this.chartLoading.set(false);
        setTimeout(() => this.drawChart(data), 0);
      },
      error: () => this.chartLoading.set(false),
    });

    if (this.hasGauges) {
      this.lora.getDashboardGauges(this.group.type, this.group.id, field, this.period()).subscribe({
        next: g => this.gauges.set(g.gauges),
      });
    } else {
      this.gauges.set([]);
    }
  }

  private drawChart(data: DashboardChartResult): void {
    const div = this.plotRef?.nativeElement;
    if (!div) return;

    const series  = data.sensors;
    const weather = data.weather;

    const rootStyle     = getComputedStyle(document.documentElement);
    const gridColor     = rootStyle.getPropertyValue('--border').trim();
    const axisTextColor = rootStyle.getPropertyValue('--text-mute').trim();
    const cardColor     = rootStyle.getPropertyValue('--card').trim();
    const textColor     = rootStyle.getPropertyValue('--text').trim();
    const fontFamily    = rootStyle.getPropertyValue('--font-ui').trim();

    // Aire pleine (wash ~15%) réservée à une seule série : superposer plusieurs
    // remplissages translucides brouille les couleurs — au-delà, lignes nues.
    // La prévision météo compte dans ce décompte : une aire pleine sous une
    // courbe en pointillés rend les deux illisibles.
    const singleSeries = series.length === 1 && !weather;
    const unit = this.unit;

    const traces: Plotly.Data[] = series.map(s => {
      const color = this.colorForSensor(s.sensor_id);
      return {
        type: 'scatter',
        mode: 'lines',
        name: s.name,
        x: s.points.map(p => p.t),
        y: s.points.map(p => p.v),
        line: { color, width: 2, shape: 'spline', smoothing: 0.4 },
        fill: singleSeries ? 'tozeroy' : 'none',
        fillcolor: singleSeries ? color + '26' : undefined,
        hovertemplate: `%{y:.1f}${unit}<extra>${s.name}</extra>`,
        connectgaps: false,
      };
    });

    // La prévision n'est pas un capteur : elle reste hors de la palette
    // catégorielle (--series-N, identité d'un capteur) et se lit comme du
    // contexte — trait en pointillés, gris de texte secondaire.
    if (weather && weather.points.length) {
      const label = `Prévision ${weather.location}`;
      traces.push({
        type: 'scatter',
        mode: 'lines',
        name: label,
        x: weather.points.map(p => p.t),
        y: weather.points.map(p => p.v),
        line: { color: axisTextColor, width: 2, dash: 'dot', shape: 'spline', smoothing: 0.4 },
        fill: 'none',
        hovertemplate: `%{y:.1f}${unit}<extra>${label}</extra>`,
        connectgaps: false,
      });
    }

    const layout: Partial<Plotly.Layout> = {
      autosize: true,
      height: 320,
      margin: { l: 46, r: 16, t: traces.length > 1 ? 36 : 12, b: 32 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      font: { family: fontFamily, color: axisTextColor, size: 12 },
      xaxis: {
        type: 'date',
        showgrid: false,
        showline: true,
        linecolor: gridColor,
        tickfont: { color: axisTextColor, size: 11 },
      },
      yaxis: {
        showgrid: true,
        gridcolor: gridColor,
        zeroline: false,
        showline: false,
        ticksuffix: unit,
        tickfont: { color: axisTextColor, size: 11 },
      },
      showlegend: traces.length > 1,
      legend: { orientation: 'h', x: 1, xanchor: 'right', y: 1.02, yanchor: 'bottom', font: { color: axisTextColor, size: 12 } },
      hovermode: 'x unified',
      hoverlabel: {
        bgcolor: cardColor,
        bordercolor: gridColor,
        font: { color: textColor, size: 12, family: fontFamily },
      },
    };

    const config: Partial<Plotly.Config> = {
      displayModeBar: false,
      responsive: true,
    };

    Plotly.react(div, traces, layout, config);
    this.plotted = true;
  }
}
