import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { IonicModule } from '@ionic/angular';
import { RouterModule, Routes } from '@angular/router';

import { LoginPage } from './login/login.page';
import { RegisterPage } from './register/register.page';
import { ResetPasswordPage } from './reset-password/reset-password.page';
import { SetPasswordPage } from './set-password/set-password.page';

const routes: Routes = [
  { path: 'login', component: LoginPage },
  { path: 'register', component: RegisterPage },
  { path: 'reset-password', component: ResetPasswordPage },
  { path: 'set-password', component: SetPasswordPage },
  { path: '', redirectTo: 'login', pathMatch: 'full' },
];

@NgModule({
  declarations: [LoginPage, RegisterPage, ResetPasswordPage, SetPasswordPage],
  imports: [CommonModule, ReactiveFormsModule, IonicModule, RouterModule.forChild(routes)],
})
export class AuthModule {}
