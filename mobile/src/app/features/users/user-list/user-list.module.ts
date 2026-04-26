import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { UserListPage } from './user-list.page';

const routes: Routes = [{ path: '', component: UserListPage }];

@NgModule({
  declarations: [UserListPage],
  imports: [CommonModule, IonicModule, RouterModule.forChild(routes)],
})
export class UserListModule {}
