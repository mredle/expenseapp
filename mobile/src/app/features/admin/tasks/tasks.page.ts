import { Component, OnInit } from '@angular/core';
import { AlertController, ToastController } from '@ionic/angular';
import { ApiService } from '../../../core/services/api.service';
import { Task } from '../../../core/models/models';

@Component({ standalone: false, selector: 'app-tasks', templateUrl: 'tasks.page.html' })
export class TasksPage implements OnInit {
  tasks: Task[] = [];
  loading = true;
  showComplete = false;

  constructor(private api: ApiService, private alert: AlertController, private toast: ToastController) {}
  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading = true;
    this.api.getTasks(1, 50, this.showComplete ? undefined : false).subscribe({
      next: res => { this.tasks = res.items; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  confirmDelete(t: Task): void {
    this.alert.create({
      header: 'Delete Task',
      message: `Delete task "${t.name}"?`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Delete', role: 'destructive', handler: () => {
          this.api.deleteTask(t.id).subscribe({
            next: () => { this.load(); this.showToast('Task deleted.'); },
            error: () => this.showToast('Error deleting task.', true),
          });
        }},
      ],
    }).then(a => a.present());
  }

  launchCurrencyUpdate(): void {
    this.api.launchTask('update-currencies').subscribe({
      next: () => { this.showToast('Currency update task launched.'); this.load(); },
      error: () => this.showToast('Error launching task.', true),
    });
  }

  private showToast(msg: string, error = false): void {
    this.toast.create({ message: msg, duration: 2500, color: error ? 'danger' : 'success', position: 'bottom' })
      .then(t => t.present());
  }
}
