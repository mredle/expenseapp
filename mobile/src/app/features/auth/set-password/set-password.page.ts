import { Component, OnInit } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { LoadingController, ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';

@Component({ standalone: false, selector: 'app-set-password', templateUrl: 'set-password.page.html' })
export class SetPasswordPage implements OnInit {
  form = this.fb.group({
    token: ['', Validators.required],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  constructor(private fb: FormBuilder, private api: ApiService, private router: Router, private route: ActivatedRoute, private loadingCtrl: LoadingController, private toastCtrl: ToastController) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (token) this.form.patchValue({ token });
  }

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    const loading = await this.loadingCtrl.create({ message: 'Setting password…' });
    await loading.present();
    const { token, password } = this.form.value;
    this.api.setPassword(token!, password!).subscribe({
      next: async () => {
        loading.dismiss();
        const t = await this.toastCtrl.create({ message: 'Password set! You can now log in.', duration: 3000, color: 'success' });
        await t.present();
        this.router.navigate(['/auth/login']);
      },
      error: async (e) => { loading.dismiss(); const t = await this.toastCtrl.create({ message: e.error?.message || 'Error', duration: 3000, color: 'danger' }); await t.present(); },
    });
  }
}
