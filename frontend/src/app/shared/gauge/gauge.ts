import { Component, Input } from '@angular/core';

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

/** Arc SVG (demi-cercle) allant de startAngle à endAngle, en degrés (180=gauche/min, 0=droite/max). */
function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end   = polarToCartesian(cx, cy, r, endAngle);
  const largeArcFlag = startAngle - endAngle <= 180 ? 0 : 1;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 1 ${end.x} ${end.y}`;
}

@Component({
  selector: 'app-gauge',
  standalone: true,
  templateUrl: './gauge.html',
  styleUrl: './gauge.scss',
})
export class GaugeComponent {
  @Input({ required: true }) label!: string;
  @Input({ required: true }) value: number | null = null;
  @Input({ required: true }) min = 0;
  @Input({ required: true }) max = 1;
  @Input() unit = '';
  @Input() color = 'var(--accent)';
  @Input() referenceValue: number | null = null;
  @Input() referenceLabel = '';
  @Input() delta: number | null = null;
  @Input() deltaColor: 'red' | 'green' | null = null;

  private readonly cx = 100;
  private readonly cy = 92;
  private readonly r  = 76;

  private _angleFor(v: number): number {
    const span = this.max - this.min || 1;
    const pct = Math.min(1, Math.max(0, (v - this.min) / span));
    return 180 - pct * 180;
  }

  get trackPath(): string {
    return describeArc(this.cx, this.cy, this.r, 180, 0);
  }

  get valuePath(): string | null {
    if (this.value == null) return null;
    return describeArc(this.cx, this.cy, this.r, 180, this._angleFor(this.value));
  }

  get referenceMarker(): { x1: number; y1: number; x2: number; y2: number } | null {
    if (this.referenceValue == null) return null;
    const angle = this._angleFor(this.referenceValue);
    const inner = polarToCartesian(this.cx, this.cy, this.r - 12, angle);
    const outer = polarToCartesian(this.cx, this.cy, this.r + 12, angle);
    return { x1: inner.x, y1: inner.y, x2: outer.x, y2: outer.y };
  }

  get formattedValue(): string {
    return this.value == null ? '—' : `${this.value.toFixed(1)}${this.unit}`;
  }

  get formattedDelta(): string | null {
    if (this.delta == null) return null;
    const sign = this.delta >= 0 ? '+' : '−';
    return `${sign}${Math.abs(this.delta).toFixed(1)}${this.unit}`;
  }

  get formattedMin(): string { return this.min.toFixed(0); }
  get formattedMax(): string { return this.max.toFixed(0); }
}
