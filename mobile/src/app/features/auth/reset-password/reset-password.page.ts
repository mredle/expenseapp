import { Component } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { LoadingController, ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';

@Component({ standalone: false, selector: 'app-reset-password', templateUrl: 'reset-password.page.html' })
export class ResetPasswordPage {
  form = this.fb.group({ email: ['', [Validators.required, Validators.email]] });

  constructor(private fb: FormBuilder, private api: ApiService, private router: Router, private loadingCtrl: LoadingController, private toastCtrl: ToastController) {}

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Sending…' });
    await loading.present();
    this.api.resetPassword(this.form.value.email!).subscribe({
      next: async () => {
        loading.dismiss();
        const t = await this.toastCtrl.create({ message: 'Check your email for reset instructions.', duration: 4000, color: 'success' });
        await t.present();
        this.router.navigate(['/auth/login']);
      },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 3000, color: 'danger' }); await t.present(); },
    });
  }
}
