import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { TabsPage } from './tabs.page';

const routes: Routes = [
  {
    path: '',
    component: TabsPage,
    children: [
      { path: 'events', loadChildren: () => import('../events/event-list/event-list.module').then(m => m.EventListModule) },
      { path: 'currencies', loadChildren: () => import('../currencies/currencies.module').then(m => m.CurrenciesModule) },
      { path: 'users', loadChildren: () => import('../users/user-list/user-list.module').then(m => m.UserListModule) },
      { path: 'messages', loadChildren: () => import('../messages/messages.module').then(m => m.MessagesModule) },
      { path: 'profile', loadChildren: () => import('../profile/profile.module').then(m => m.ProfileModule) },
      { path: '', redirectTo: 'events', pathMatch: 'full' },
    ]
  }
];

@NgModule({
  declarations: [TabsPage],
  imports: [CommonModule, IonicModule, RouterModule.forChild(routes)],
  // CommonModule provides AsyncPipe and NgIf used in the template
})
export class TabsModule {}
