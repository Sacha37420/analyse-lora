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

export interface ConnectionMethod {
  protocol: string;
  label: string;
  icon: string;
  description: string;
  fields: { key: string; label: string; placeholder: string; required: boolean }[];
  guide_steps: string[];
}

export interface ConnectionInfo {
  sensor_id: number;
  slug: string;
  protocol: string;
  connection_config: Record<string, string>;
  api_key: string;
  api_ingest_url: string;
  guide: ConnectionMethod;
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
    data: { protocol?: string; connection_config?: Record<string, string> },
  ): Observable<unknown> {
    return this.http.put(`${this.base}/api/sensors/${sensorId}/connection/`, data);
  }

  getConnectionMethods(): Observable<ConnectionMethod[]> {
    return this.http.get<ConnectionMethod[]>(`${this.base}/api/connection-methods/`);
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
