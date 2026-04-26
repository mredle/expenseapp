import { NgModule } from '@angular/core';
import { PreloadAllModules, RouterModule, Routes } from '@angular/router';
import { AuthGuard } from './core/guards/auth.guard';

const routes: Routes = [
  { path: '', redirectTo: '/tabs/events', pathMatch: 'full' },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.module').then(m => m.AuthModule)
  },
  {
    path: 'tabs',
    canActivate: [AuthGuard],
    loadChildren: () => import('./features/tabs/tabs.module').then(m => m.TabsModule)
  },
  {
    path: 'event',
    canActivate: [AuthGuard],
    loadChildren: () => import('./features/events/events.module').then(m => m.EventsModule)
  },
  {
    path: 'users/:guid',
    canActivate: [AuthGuard],
    loadChildren: () => import('./features/users/user-detail/user-detail.module').then(m => m.UserDetailModule)
  },
  {
    path: 'admin',
    canActivate: [AuthGuard],
    loadChildren: () => import('./features/admin/admin.module').then(m => m.AdminModule)
  },
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { preloadingStrategy: PreloadAllModules })],
  exports: [RouterModule]
})
export class AppRoutingModule {}
