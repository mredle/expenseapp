import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ToastController } from '@ionic/angular';
import { Router } from '@angular/router';
import { startRegistration } from '@simplewebauthn/browser';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { User } from '../../core/models/models';

@Component({ standalone: false, selector: 'app-profile', templateUrl: 'profile.page.html' })
export class ProfilePage implements OnInit {
  user: User | null = null;
  loading = true;
  editMode = false;
  form: FormGroup;
  registeringPasskey = false;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private fb: FormBuilder,
    private toast: ToastController,
    private router: Router,
  ) {
    this.form = this.fb.group({
      username: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      about_me: [''],
    });
  }

  ngOnInit(): void { this.load(); }

  load(): void {
    const guid = this.auth.userGuid;
    if (!guid) { return; }
    this.loading = true;
    this.api.getUser(guid).subscribe({
      next: u => { this.user = u; this.form.patchValue(u); this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  saveProfile(): void {
    if (!this.user || this.form.invalid) { return; }
    this.api.updateUser(this.user.id, this.form.value).subscribe({
      next: u => { this.user = u; this.editMode = false; this.showToast('Profile updated.'); },
      error: () => this.showToast('Error updating profile.', true),
    });
  }

  onPictureChange(ev: Event): void {
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (!file || !this.user) { return; }
    this.api.uploadUserPicture(this.user.id, file).subscribe({
      next: () => { this.showToast('Picture updated.'); this.load(); },
      error: () => this.showToast('Error uploading picture.', true),
    });
  }

  async registerPasskey(): Promise<void> {
    this.registeringPasskey = true;
    this.api.getWebAuthnRegisterOptions().subscribe({
      next: async ({ options, session_id }) => {
        try {
          const credential = await startRegistration(JSON.parse(options));
          this.api.verifyWebAuthnRegister(session_id, credential).subscribe({
            next: () => { this.registeringPasskey = false; this.showToast('Passkey registered!'); },
            error: () => { this.registeringPasskey = false; this.showToast('Passkey verification failed.', true); },
          });
        } catch {
          this.registeringPasskey = false;
          this.showToast('Passkey registration cancelled.', true);
        }
      },
      error: () => { this.registeringPasskey = false; this.showToast('Could not start passkey registration.', true); },
    });
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/auth/login']);
  }

  private showToast(msg: string, error = false): void {
    this.toast.create({ message: msg, duration: 2500, color: error ? 'danger' : 'success', position: 'bottom' })
      .then(t => t.present());
  }
}
