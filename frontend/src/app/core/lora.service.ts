import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

interface EnvWindow { __env?: { apiUrl?: string } }

export interface Sensor {
  id: number;
  name: string;
  slug: string;
  description: string;
  protocol: string;
  protocol_display: string;
  is_active: boolean;
  created_at: string;
  reading_count: number;
  last_reading: { timestamp: string; data: Record<string, unknown> } | null;
  user_accesses?: UserAccess[];
  connection_config?: Record<string, string>;
  api_key?: string;
  webhook?: number | null;
  webhook_name?: string | null;
  location?: 'interior' | 'exterior';
  weather_location?: string;
}

export interface WebhookSensor {
  id: number;
  name: string;
  slug: string;
  device_id: string;
}

export interface Webhook {
  id: number;
  name: string;
  protocol: string;
  protocol_display: string;
  connection_config: Record<string, string>;
  api_key: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  sensor_count: number;
  sensors: WebhookSensor[];
  user_accesses?: UserAccess[];
  weather_location?: string;
}

export interface UserAccess {
  id: number;
  user_email: string;
  granted_at: string;
}

export interface SensorReading {
  id: number;
  timestamp: string;
  data: Record<string, unknown>;
  received_at: string;
}

export interface ReadingsPage {
  count: number;
  page: number;
  page_size: number;
  results: SensorReading[];
}

export interface ComputedMeasure {
  id: number;
  sensor: number;
  name: string;
  description: string;
  formula: string;
  unit: string;
  color: string;
  created_at: string;
}

export interface MeasurePoint { t: string; v: number }

export interface MeasureResult {
  measure: ComputedMeasure;
  points: MeasurePoint[];
}

export interface ConnectionField {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
}

export interface WebhookGuide {
  fields: ConnectionField[];
  sensor_field: { key: string; label: string; placeholder: string };
  guide_steps: string[];
}

export interface ConnectionMethod {
  protocol: string;
  label: string;
  icon: string;
  description: string;
  supports_webhook: boolean;
  fields: ConnectionField[];
  guide_steps: string[];
  webhook_guide: WebhookGuide | null;
}

export interface ConnectionInfo {
  sensor_id: number;
  slug: string;
  protocol: string;
  connection_config: Record<string, string>;
  api_key: string;
  api_ingest_url: string;
  guide: ConnectionMethod;
  webhook_guide: WebhookGuide | null;
  webhook: { id: number; name: string; protocol: string } | null;
}

export type Period = 'day' | 'week' | 'month';

export interface DashboardSensorBrief {
  id: number;
  name: string;
  location: 'interior' | 'exterior';
}

export interface DashboardGroup {
  type: 'webhook' | 'sensor';
  id: number;
  name: string;
  protocol: string;
  sensors: DashboardSensorBrief[];
}

/** Compte rendu d'un rattrapage depuis la Storage Integration TTN. */
export interface TTNBackfillResult {
  /** Plus ancien uplink encore conservé par TTN — rien n'est récupérable avant. */
  available_since: string | null;
  fetched: number;
  inserted: number;
  sensors: { sensor_id: number; name: string; available: number; inserted: number }[];
  unmatched_devices: string[];
}

export interface ChartPoint { t: string; v: number }

export interface ChartSeries {
  sensor_id: number;
  name: string;
  location: string;
  points: ChartPoint[];
}

/** Prévision horaire Open-Meteo pour la localisation du groupe — grandeurs thermiques seulement. */
export interface WeatherSeries {
  location: string;
  points: ChartPoint[];
}

export interface DashboardChartResult {
  period: { start: string; end: string };
  sensors: ChartSeries[];
  /** null si la grandeur n'est pas thermique, sans localisation configurée, ou météo injoignable. */
  weather: WeatherSeries | null;
}

export interface GaugeData {
  sensor_id: number;
  name: string;
  value: number | null;
  timestamp: string | null;
  exterior_sensor_name: string | null;
  exterior_value: number | null;
  delta: number | null;
  delta_color: 'red' | 'green' | null;
  min: number;
  max: number;
  is_temperature: boolean;
}


@Injectable({ providedIn: 'root' })
export class LoraService {
  private http = inject(HttpClient);

  private get base(): string {
    return (window as unknown as EnvWindow).__env?.apiUrl ?? 'http://localhost:8086';
  }

  // ── Utilisateur ────────────────────────────────────────────────────────
  getMe(): Observable<{ email: string; username: string; groups: string[]; is_developer: boolean }> {
    return this.http.get<any>(`${this.base}/api/me/`);
  }

  // ── Capteurs ───────────────────────────────────────────────────────────
  getSensors(): Observable<Sensor[]> {
    return this.http.get<Sensor[]>(`${this.base}/api/sensors/`);
  }

  getSensor(id: number): Observable<Sensor> {
    return this.http.get<Sensor>(`${this.base}/api/sensors/${id}/`);
  }

  createSensor(data: Partial<Sensor>): Observable<Sensor> {
    return this.http.post<Sensor>(`${this.base}/api/sensors/`, data);
  }

  updateSensor(id: number, data: Partial<Sensor>): Observable<Sensor> {
    return this.http.put<Sensor>(`${this.base}/api/sensors/${id}/`, data);
  }

  deleteSensor(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/sensors/${id}/`);
  }

  // ── Accès utilisateurs ─────────────────────────────────────────────────
  getSensorUsers(sensorId: number): Observable<UserAccess[]> {
    return this.http.get<UserAccess[]>(`${this.base}/api/sensors/${sensorId}/users/`);
  }

  addSensorUser(sensorId: number, email: string): Observable<UserAccess> {
    return this.http.post<UserAccess>(`${this.base}/api/sensors/${sensorId}/users/`, { user_email: email });
  }

  removeSensorUser(sensorId: number, email: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/sensors/${sensorId}/users/${email}/`);
  }

  // ── Données capteur ────────────────────────────────────────────────────
  getSensorData(
    sensorId: number,
    opts: { start?: string; end?: string; page?: number; page_size?: number } = {},
  ): Observable<ReadingsPage> {
    let params = new HttpParams();
    if (opts.start)     params = params.set('start',     opts.start);
    if (opts.end)       params = params.set('end',       opts.end);
    if (opts.page)      params = params.set('page',      opts.page);
    if (opts.page_size) params = params.set('page_size', opts.page_size);
    return this.http.get<ReadingsPage>(`${this.base}/api/sensors/${sensorId}/data/`, { params });
  }

  // ── Connexion ──────────────────────────────────────────────────────────
  getConnectionInfo(sensorId: number): Observable<ConnectionInfo> {
    return this.http.get<ConnectionInfo>(`${this.base}/api/sensors/${sensorId}/connection/`);
  }

  updateConnectionConfig(
    sensorId: number,
    data: { protocol?: string; connection_config?: Record<string, string>; webhook?: number | null },
  ): Observable<unknown> {
    return this.http.put(`${this.base}/api/sensors/${sensorId}/connection/`, data);
  }

  getConnectionMethods(): Observable<ConnectionMethod[]> {
    return this.http.get<ConnectionMethod[]>(`${this.base}/api/connection-methods/`);
  }

  // ── Webhooks ───────────────────────────────────────────────────────────
  getWebhooks(): Observable<Webhook[]> {
    return this.http.get<Webhook[]>(`${this.base}/api/webhooks/`);
  }

  getWebhook(id: number): Observable<Webhook> {
    return this.http.get<Webhook>(`${this.base}/api/webhooks/${id}/`);
  }

  createWebhook(data: { name: string; protocol: string; connection_config: Record<string, string>; is_active?: boolean }): Observable<Webhook> {
    return this.http.post<Webhook>(`${this.base}/api/webhooks/`, data);
  }

  updateWebhook(id: number, data: Partial<Webhook>): Observable<Webhook> {
    return this.http.put<Webhook>(`${this.base}/api/webhooks/${id}/`, data);
  }

  deleteWebhook(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/webhooks/${id}/`);
  }

  // ── Accès utilisateurs (webhook) ───────────────────────────────────────
  getWebhookUsers(webhookId: number): Observable<UserAccess[]> {
    return this.http.get<UserAccess[]>(`${this.base}/api/webhooks/${webhookId}/users/`);
  }

  addWebhookUser(webhookId: number, email: string): Observable<UserAccess> {
    return this.http.post<UserAccess>(`${this.base}/api/webhooks/${webhookId}/users/`, { user_email: email });
  }

  removeWebhookUser(webhookId: number, email: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/webhooks/${webhookId}/users/${email}/`);
  }

  // ── Tableau de bord ────────────────────────────────────────────────────
  getDashboardGroups(): Observable<DashboardGroup[]> {
    return this.http.get<DashboardGroup[]>(`${this.base}/api/dashboard/groups/`);
  }

  getDashboardFields(type: string, id: number): Observable<string[]> {
    return this.http.get<string[]>(`${this.base}/api/dashboard/groups/${type}/${id}/fields/`);
  }

  getDashboardChart(type: string, id: number, field: string, period: Period): Observable<DashboardChartResult> {
    const params = new HttpParams().set('field', field).set('period', period);
    return this.http.get<DashboardChartResult>(`${this.base}/api/dashboard/groups/${type}/${id}/chart/`, { params });
  }

  getDashboardGauges(type: string, id: number, field: string, period: Period): Observable<{ gauges: GaugeData[] }> {
    const params = new HttpParams().set('field', field).set('period', period);
    return this.http.get<{ gauges: GaugeData[] }>(`${this.base}/api/dashboard/groups/${type}/${id}/gauges/`, { params });
  }

  ttnBackfill(type: string, id: number): Observable<TTNBackfillResult> {
    return this.http.post<TTNBackfillResult>(`${this.base}/api/dashboard/groups/${type}/${id}/ttn-backfill/`, {});
  }

  // ── Météo (config par webhook, ou par capteur autonome) ─────────────────
  updateWebhookWeather(id: number, data: { weather_location: string }): Observable<Webhook> {
    return this.http.patch<Webhook>(`${this.base}/api/webhooks/${id}/`, data);
  }

  updateSensorWeather(id: number, data: { weather_location: string }): Observable<Sensor> {
    return this.http.patch<Sensor>(`${this.base}/api/sensors/${id}/`, data);
  }

  // ── Grandeurs calculées ────────────────────────────────────────────────
  getMeasures(sensorId: number): Observable<ComputedMeasure[]> {
    return this.http.get<ComputedMeasure[]>(`${this.base}/api/sensors/${sensorId}/measures/`);
  }

  createMeasure(sensorId: number, data: Partial<ComputedMeasure>): Observable<ComputedMeasure> {
    return this.http.post<ComputedMeasure>(`${this.base}/api/sensors/${sensorId}/measures/`, data);
  }

  updateMeasure(measureId: number, data: Partial<ComputedMeasure>): Observable<ComputedMeasure> {
    return this.http.put<ComputedMeasure>(`${this.base}/api/measures/${measureId}/`, data);
  }

  deleteMeasure(measureId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/measures/${measureId}/`);
  }

  computeMeasure(
    measureId: number,
    opts: { start?: string; end?: string } = {},
  ): Observable<MeasureResult> {
    let params = new HttpParams();
    if (opts.start) params = params.set('start', opts.start);
    if (opts.end)   params = params.set('end',   opts.end);
    return this.http.get<MeasureResult>(`${this.base}/api/measures/${measureId}/compute/`, { params });
  }
}
