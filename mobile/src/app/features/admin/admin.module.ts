import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { AdminPage } from './admin.page';
import { LogsPage } from './logs/logs.page';
import { TasksPage } from './tasks/tasks.page';
import { StatisticsPage } from './statistics/statistics.page';

const routes: Routes = [
  {
    path: '', component: AdminPage,
    children: [
      { path: 'logs', component: LogsPage },
      { path: 'tasks', component: TasksPage },
      { path: 'statistics', component: StatisticsPage },
      { path: '', redirectTo: 'logs', pathMatch: 'full' },
    ]
  }
];

@NgModule({
  declarations: [AdminPage, LogsPage, TasksPage, StatisticsPage],
  imports: [CommonModule, FormsModule, IonicModule, RouterModule.forChild(routes)],
})
export class AdminModule {}
