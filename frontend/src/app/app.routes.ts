import { Routes } from '@angular/router';
import { developerGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home/home').then(m => m.HomeComponent),
  },
  {
    path: 'sensors',
    loadComponent: () => import('./pages/sensors/sensor-list').then(m => m.SensorListComponent),
  },
  {
    path: 'sensors/:id/data',
    loadComponent: () => import('./pages/sensors/sensor-detail').then(m => m.SensorDetailComponent),
  },
  {
    path: 'sensors/:id/measures',
    loadComponent: () => import('./pages/measures/measure-view').then(m => m.MeasureViewComponent),
  },
  {
    path: 'admin/sensors',
    canActivate: [developerGuard],
    loadComponent: () => import('./pages/admin/sensor-admin').then(m => m.SensorAdminComponent),
  },
  {
    path: 'admin/sensors/:id',
    canActivate: [developerGuard],
    loadComponent: () => import('./pages/admin/sensor-admin').then(m => m.SensorAdminComponent),
  },
  {
    path: 'admin/sensors/:id/connection',
    canActivate: [developerGuard],
    loadComponent: () => import('./pages/admin/sensor-connection').then(m => m.SensorConnectionComponent),
  },
  {
    path: 'profile',
    loadComponent: () => import('./pages/profile/profile').then(m => m.ProfileComponent),
  },
  { path: '**', redirectTo: '' },
];
