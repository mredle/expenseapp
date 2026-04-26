import { Component } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { LoadingController, ToastController } from '@ionic/angular';
import { AuthService } from '../../../core/services/auth.service';
import { ApiService } from '../../../core/services/api.service';
import {
  browserSupportsWebAuthn,
  startAuthentication,
} from '@simplewebauthn/browser';

@Component({
  standalone: false,
  selector: 'app-login',
  templateUrl: 'login.page.html',
})
export class LoginPage {
  form = this.fb.group({
    username: ['', Validators.required],
    password: ['', Validators.required],
  });
  showPassword = false;
  webAuthnSupported = browserSupportsWebAuthn();

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private api: ApiService,
    private router: Router,
    private loadingCtrl: LoadingController,
    private toastCtrl: ToastController,
  ) {}

  async loginPassword(): Promise<void> {
    if (this.form.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Signing in…' });
    await loading.present();
    const { username, password } = this.form.value;
    this.auth.loginPassword(username!, password!).subscribe({
      next: () => { loading.dismiss(); this.router.navigate(['/tabs/events']); },
      error: async (e) => {
        loading.dismiss();
        await this.showToast(e.error?.message || 'Login failed');
      },
    });
  }

  async loginWebAuthn(): Promise<void> {
    const loading = await this.loadingCtrl.create({ message: 'Preparing passkey…' });
    await loading.present();
    this.api.getWebAuthnAuthOptions().subscribe({
      next: async (res) => {
        loading.dismiss();
        try {
          const options = JSON.parse(res.options);
          const credential = await startAuthentication({ optionsJSON: options });
          const loading2 = await this.loadingCtrl.create({ message: 'Verifying…' });
          await loading2.present();
          this.auth.loginWebAuthn(res.session_id, credential).subscribe({
            next: () => { loading2.dismiss(); this.router.navigate(['/tabs/events']); },
            error: async (e) => { loading2.dismiss(); await this.showToast(e.error?.message || 'Passkey verification failed'); },
          });
        } catch (err: any) {
          await this.showToast(err.message || 'Passkey authentication cancelled');
        }
      },
      error: async (e) => { loading.dismiss(); await this.showToast(e.error?.message || 'Could not get passkey options'); },
    });
  }

  private async showToast(msg: string): Promise<void> {
    const t = await this.toastCtrl.create({ message: msg, duration: 3000, color: 'danger' });
    await t.present();
  }
}
