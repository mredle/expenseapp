import { Component } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { LoadingController, ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';

@Component({ standalone: false, selector: 'app-register', templateUrl: 'register.page.html' })
export class RegisterPage {
  form = this.fb.group({
    username: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email]],
    locale: ['en'],
  });

  constructor(
    private fb: FormBuilder,
    private api: ApiService,
    private router: Router,
    private loadingCtrl: LoadingController,
    private toastCtrl: ToastController,
  ) {}

  async register(): Promise<void> {
    if (this.form.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Creating account…' });
    await loading.present();
    const { username, email, locale } = this.form.value;
    this.api.register(username!, email!, locale!).subscribe({
      next: async () => {
        loading.dismiss();
        const t = await this.toastCtrl.create({ message: 'Account created! Check your email for next steps.', duration: 4000, color: 'success' });
        await t.present();
        this.router.navigate(['/auth/login']);
      },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Registration failed', duration: 3000, color: 'danger' }); await t.present(); },
    });
  }
}
