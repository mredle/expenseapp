import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { UserDetailPage } from './user-detail.page';

const routes: Routes = [{ path: '', component: UserDetailPage }];

@NgModule({
  declarations: [UserDetailPage],
  imports: [CommonModule, FormsModule, ReactiveFormsModule, IonicModule, RouterModule.forChild(routes)],
})
export class UserDetailModule {}
