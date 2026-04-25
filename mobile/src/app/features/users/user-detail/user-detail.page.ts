import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { AuthService } from '../../../core/services/auth.service';
import { User } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-user-detail', templateUrl: 'user-detail.page.html' })
export class UserDetailPage implements OnInit {
  user: User | null = null;
  loading = true;
  isAdmin = false;
  isSelf = false;
  form: FormGroup;
  editMode = false;

  constructor(
    private route: ActivatedRoute,
    private api: ApiService,
    private auth: AuthService,
    private fb: FormBuilder,
    private toast: ToastController,
  ) {
    this.form = this.fb.group({
      username: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      about_me: [''],
    });
  }

  ngOnInit(): void {
    const guid = this.route.snapshot.paramMap.get('guid')!;
    this.loadCurrentUser(guid);
    this.loadUser(guid);
  }

  private loadCurrentUser(targetGuid: string): void {
    const myGuid = this.auth.userGuid;
    if (myGuid) {
      this.api.getUser(myGuid).subscribe({
        next: u => {
          this.isAdmin = !!u.is_admin;
          this.isSelf = myGuid === targetGuid;
        },
      });
    }
  }

  private loadUser(guid: string): void {
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

  toggleAdmin(): void {
    if (!this.user) { return; }
    this.api.setUserAdmin(this.user.id, !this.user.is_admin).subscribe({
      next: u => { this.user = u; this.showToast(`Admin ${u.is_admin ? 'granted' : 'revoked'}.`); },
      error: () => this.showToast('Error toggling admin.', true),
    });
  }

  onPictureChange(ev: Event): void {
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (!file || !this.user) { return; }
    this.api.uploadUserPicture(this.user.id, file).subscribe({
      next: () => { this.showToast('Picture updated.'); this.loadUser(this.user!.id); },
      error: () => this.showToast('Error uploading picture.', true),
    });
  }

  private showToast(msg: string, error = false): void {
    this.toast.create({ message: msg, duration: 2500, color: error ? 'danger' : 'success', position: 'bottom' })
      .then(t => t.present());
  }
}
