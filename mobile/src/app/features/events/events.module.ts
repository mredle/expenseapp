import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';

import { EventMainPage } from './event-main/event-main.page';
import { EventSettingsPage } from './event-settings/event-settings.page';
import { ExpensesPage } from './expenses/expenses.page';
import { ExpenseDetailPage } from './expense-detail/expense-detail.page';
import { SettlementsPage } from './settlements/settlements.page';
import { BalancePage } from './balance/balance.page';
import { EventUsersPage } from './event-users/event-users.page';
import { EventUserDetailPage } from './event-user-detail/event-user-detail.page';
import { EventCurrenciesPage } from './event-currencies/event-currencies.page';

const routes: Routes = [
  { path: 'new/settings', component: EventSettingsPage },
  { path: ':guid/main', component: EventMainPage },
  { path: ':guid/settings', component: EventSettingsPage },
  { path: ':guid/expenses', component: ExpensesPage },
  { path: ':guid/expenses/:expenseGuid', component: ExpenseDetailPage },
  { path: ':guid/settlements', component: SettlementsPage },
  { path: ':guid/balance', component: BalancePage },
  { path: ':guid/users', component: EventUsersPage },
  { path: ':guid/users/:userGuid', component: EventUserDetailPage },
  { path: ':guid/currencies', component: EventCurrenciesPage },
];

@NgModule({
  declarations: [
    EventMainPage, EventSettingsPage, ExpensesPage, ExpenseDetailPage,
    SettlementsPage, BalancePage, EventUsersPage, EventUserDetailPage, EventCurrenciesPage,
  ],
  imports: [CommonModule, ReactiveFormsModule, FormsModule, IonicModule, RouterModule.forChild(routes)],
})
export class EventsModule {}
