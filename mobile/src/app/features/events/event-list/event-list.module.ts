import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { EventListPage } from './event-list.page';

const routes: Routes = [{ path: '', component: EventListPage }];

@NgModule({
  declarations: [EventListPage],
  imports: [CommonModule, IonicModule, RouterModule.forChild(routes)],
})
export class EventListModule {}
