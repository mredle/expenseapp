import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';
import { CurrenciesPage } from './currencies.page';

const routes: Routes = [{ path: '', component: CurrenciesPage }];

@NgModule({
  declarations: [CurrenciesPage],
  imports: [CommonModule, FormsModule, ReactiveFormsModule, IonicModule, RouterModule.forChild(routes)],
})
export class CurrenciesModule {}
