import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AuthResult, TokenResponse, User, UserCollection,
  Currency, PaginatedResponse, Event, EventUser, EventCurrency,
  Expense, Settlement, Post, Balance, Message, Notification,
  Log, Task, Stat, ImageMeta
} from '../models/models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  private url(path: string): string {
    return `${this.base}${path}`;
  }

  private params(obj: Record<string, any>): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(obj)) {
      if (v !== undefined && v !== null) p = p.set(k, String(v));
    }
    return p;
  }

  // ── Auth ─────────────────────────────────────────────────────────────────

  login(username: string, password: string): Observable<AuthResult> {
    return this.http.post<AuthResult>(this.url('/auth/login'), { username, password });
  }

  register(username: string, email: string, locale = 'en'): Observable<{ guid: string; username: string; email: string }> {
    return this.http.post<any>(this.url('/auth/register'), { username, email, locale });
  }

  resetPassword(email: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url('/auth/reset-password'), { email });
  }

  setPassword(token: string, password: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url('/auth/set-password'), { token, password });
  }

  getWebAuthnAuthOptions(): Observable<{ options: string; session_id: string }> {
    return this.http.post<any>(this.url('/auth/webauthn/authenticate/options'), {});
  }

  verifyWebAuthnAuth(session_id: string, credential: any): Observable<AuthResult> {
    return this.http.post<AuthResult>(this.url('/auth/webauthn/authenticate/verify'), { session_id, credential });
  }

  getWebAuthnRegisterOptions(): Observable<{ options: string; session_id: string }> {
    return this.http.post<any>(this.url('/auth/webauthn/register/options'), {});
  }

  verifyWebAuthnRegister(session_id: string, credential: any): Observable<{ message: string }> {
    return this.http.post<any>(this.url('/auth/webauthn/register/verify'), { session_id, credential });
  }

  revokeToken(): Observable<void> {
    return this.http.delete<void>(this.url('/tokens/'));
  }

  // ── Users ─────────────────────────────────────────────────────────────────

  getUsers(page = 1, per_page = 25): Observable<UserCollection> {
    return this.http.get<UserCollection>(this.url('/users/'), { params: this.params({ page, per_page }) });
  }

  getUser(guid: string): Observable<User> {
    return this.http.get<User>(this.url(`/users/${guid}`));
  }

  updateUser(guid: string, data: Partial<User>): Observable<User> {
    return this.http.put<User>(this.url(`/users/${guid}`), data);
  }

  createUser(data: { username: string; email: string; locale?: string }): Observable<User> {
    return this.http.post<User>(this.url('/users/'), data);
  }

  uploadUserPicture(guid: string, file: File): Observable<ImageMeta> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ImageMeta>(this.url(`/users/${guid}/picture`), fd);
  }

  setUserAdmin(guid: string, isAdmin: boolean): Observable<User> {
    return this.http.put<User>(this.url(`/users/${guid}/admin`), { is_admin: isAdmin });
  }

  // ── Currencies ─────────────────────────────────────────────────────────────

  getCurrencies(page = 1, per_page = 50): Observable<PaginatedResponse<Currency>> {
    return this.http.get<PaginatedResponse<Currency>>(this.url('/currencies/'), { params: this.params({ page, per_page }) });
  }

  getCurrency(guid: string): Observable<Currency> {
    return this.http.get<Currency>(this.url(`/currencies/${guid}`));
  }

  createCurrency(data: Partial<Currency>): Observable<Currency> {
    return this.http.post<Currency>(this.url('/currencies/'), data);
  }

  updateCurrency(guid: string, data: Partial<Currency>): Observable<Currency> {
    return this.http.put<Currency>(this.url(`/currencies/${guid}`), data);
  }

  // ── Events ─────────────────────────────────────────────────────────────────

  getEvents(page = 1, per_page = 25): Observable<PaginatedResponse<Event>> {
    return this.http.get<PaginatedResponse<Event>>(this.url('/events/'), { params: this.params({ page, per_page }) });
  }

  getEvent(guid: string): Observable<Event> {
    return this.http.get<Event>(this.url(`/events/${guid}`));
  }

  createEvent(data: any): Observable<Event> {
    return this.http.post<Event>(this.url('/events/'), data);
  }

  updateEvent(guid: string, data: any): Observable<Event> {
    return this.http.put<Event>(this.url(`/events/${guid}`), data);
  }

  uploadEventPicture(guid: string, file: File): Observable<ImageMeta> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ImageMeta>(this.url(`/events/${guid}/picture`), fd);
  }

  closeEvent(guid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${guid}/close`), {});
  }

  reopenEvent(guid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${guid}/reopen`), {});
  }

  convertCurrencies(guid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${guid}/convert-currencies`), {});
  }

  sendReminders(guid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${guid}/send-reminders`), {});
  }

  requestBalance(guid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${guid}/request-balance`), {});
  }

  // ── Event Users ─────────────────────────────────────────────────────────────

  getEventUsers(eventGuid: string, page = 1, per_page = 50): Observable<PaginatedResponse<EventUser>> {
    return this.http.get<PaginatedResponse<EventUser>>(this.url(`/events/${eventGuid}/users`), { params: this.params({ page, per_page }) });
  }

  getEventUser(eventGuid: string, userGuid: string): Observable<EventUser> {
    return this.http.get<EventUser>(this.url(`/events/${eventGuid}/users/${userGuid}`));
  }

  addEventUser(eventGuid: string, data: any): Observable<EventUser> {
    return this.http.post<EventUser>(this.url(`/events/${eventGuid}/users`), data);
  }

  removeEventUser(eventGuid: string, userGuid: string): Observable<{ message: string }> {
    return this.http.delete<any>(this.url(`/events/${eventGuid}/users/${userGuid}`));
  }

  readdEventUser(eventGuid: string, userGuid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${eventGuid}/users/${userGuid}/readd`), {});
  }

  updateEventUserProfile(eventGuid: string, userGuid: string, data: any, euGuid?: string): Observable<EventUser> {
    return this.http.put<EventUser>(this.url(`/events/${eventGuid}/users/${userGuid}/profile`), data, { headers: this.euHeaders(euGuid) });
  }

  updateEventUserBank(eventGuid: string, userGuid: string, data: any, euGuid?: string): Observable<{ message: string }> {
    return this.http.put<any>(this.url(`/events/${eventGuid}/users/${userGuid}/bank`), data, { headers: this.euHeaders(euGuid) });
  }

  uploadEventUserPicture(eventGuid: string, userGuid: string, file: File): Observable<ImageMeta> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ImageMeta>(this.url(`/events/${eventGuid}/users/${userGuid}/picture`), fd);
  }

  // ── Event Currencies ─────────────────────────────────────────────────────────────

  getEventCurrencies(eventGuid: string): Observable<{ items: EventCurrency[]; total: number }> {
    return this.http.get<any>(this.url(`/events/${eventGuid}/currencies`));
  }

  setEventCurrencyRate(eventGuid: string, currencyGuid: string, rate: number): Observable<{ message: string }> {
    return this.http.put<any>(this.url(`/events/${eventGuid}/currencies/${currencyGuid}/rate`), { rate });
  }

  // ── Expenses ─────────────────────────────────────────────────────────────

  getExpenses(eventGuid: string, page = 1, per_page = 25, own = false, euGuid?: string): Observable<PaginatedResponse<Expense>> {
    return this.http.get<PaginatedResponse<Expense>>(
      this.url(`/events/${eventGuid}/expenses`),
      { params: this.params({ page, per_page, own: own || undefined }), headers: this.euHeaders(euGuid) }
    );
  }

  getExpense(eventGuid: string, expenseGuid: string): Observable<Expense> {
    return this.http.get<Expense>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}`));
  }

  createExpense(eventGuid: string, data: any, euGuid?: string): Observable<Expense> {
    return this.http.post<Expense>(this.url(`/events/${eventGuid}/expenses`), data, { headers: this.euHeaders(euGuid) });
  }

  updateExpense(eventGuid: string, expenseGuid: string, data: any, euGuid?: string): Observable<Expense> {
    return this.http.put<Expense>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}`), data, { headers: this.euHeaders(euGuid) });
  }

  deleteExpense(eventGuid: string, expenseGuid: string, euGuid?: string): Observable<{ message: string }> {
    return this.http.delete<any>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}`), { headers: this.euHeaders(euGuid) });
  }

  getExpenseUsers(eventGuid: string, expenseGuid: string): Observable<PaginatedResponse<EventUser>> {
    return this.http.get<PaginatedResponse<EventUser>>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}/users`));
  }

  addExpenseUser(eventGuid: string, expenseGuid: string, userGuid: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}/users/${userGuid}`), {});
  }

  removeExpenseUser(eventGuid: string, expenseGuid: string, userGuid: string): Observable<{ message: string }> {
    return this.http.delete<any>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}/users/${userGuid}`));
  }

  uploadReceipt(eventGuid: string, expenseGuid: string, file: File): Observable<ImageMeta> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ImageMeta>(this.url(`/events/${eventGuid}/expenses/${expenseGuid}/receipt`), fd);
  }

  // ── Settlements ─────────────────────────────────────────────────────────────

  getSettlements(eventGuid: string, page = 1, per_page = 25, draft?: boolean, euGuid?: string): Observable<PaginatedResponse<Settlement>> {
    return this.http.get<PaginatedResponse<Settlement>>(
      this.url(`/events/${eventGuid}/settlements`),
      { params: this.params({ page, per_page, draft }), headers: this.euHeaders(euGuid) }
    );
  }

  createSettlement(eventGuid: string, data: any, euGuid?: string): Observable<Settlement> {
    return this.http.post<Settlement>(this.url(`/events/${eventGuid}/settlements`), data, { headers: this.euHeaders(euGuid) });
  }

  updateSettlement(eventGuid: string, settlementGuid: string, data: any, euGuid?: string): Observable<Settlement> {
    return this.http.put<Settlement>(this.url(`/events/${eventGuid}/settlements/${settlementGuid}`), data, { headers: this.euHeaders(euGuid) });
  }

  deleteSettlement(eventGuid: string, settlementGuid: string, euGuid?: string): Observable<{ message: string }> {
    return this.http.delete<any>(this.url(`/events/${eventGuid}/settlements/${settlementGuid}`), { headers: this.euHeaders(euGuid) });
  }

  confirmSettlement(eventGuid: string, settlementGuid: string, euGuid?: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/events/${eventGuid}/settlements/${settlementGuid}/confirm`), {}, { headers: this.euHeaders(euGuid) });
  }

  // ── Posts ─────────────────────────────────────────────────────────────

  getPosts(eventGuid: string, page = 1, per_page = 25): Observable<PaginatedResponse<Post>> {
    return this.http.get<PaginatedResponse<Post>>(this.url(`/events/${eventGuid}/posts`), { params: this.params({ page, per_page }) });
  }

  createPost(eventGuid: string, body: string, euGuid?: string): Observable<Post> {
    return this.http.post<Post>(this.url(`/events/${eventGuid}/posts`), { body }, { headers: this.euHeaders(euGuid) });
  }

  // ── Balance ─────────────────────────────────────────────────────────────

  getBalance(eventGuid: string): Observable<any> {
    return this.http.get<any>(this.url(`/events/${eventGuid}/balance`));
  }

  // ── Messages ─────────────────────────────────────────────────────────────

  getMessages(page = 1, per_page = 25): Observable<PaginatedResponse<Message>> {
    return this.http.get<PaginatedResponse<Message>>(this.url('/messages/'), { params: this.params({ page, per_page }) });
  }

  sendMessage(recipient_id: number, body: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url('/messages/'), { recipient_id, body });
  }

  getNotifications(since = 0): Observable<{ items: Notification[] }> {
    return this.http.get<any>(this.url('/messages/notifications'), { params: this.params({ since }) });
  }

  // ── Admin ─────────────────────────────────────────────────────────────

  getLogs(page = 1, per_page = 25, severity?: string): Observable<PaginatedResponse<Log>> {
    return this.http.get<PaginatedResponse<Log>>(this.url('/admin/logs'), { params: this.params({ page, per_page, severity }) });
  }

  getLog(id: number): Observable<Log> {
    return this.http.get<Log>(this.url(`/admin/logs/${id}`));
  }

  getTasks(page = 1, per_page = 25, complete?: boolean): Observable<PaginatedResponse<Task>> {
    return this.http.get<PaginatedResponse<Task>>(this.url('/admin/tasks'), { params: this.params({ page, per_page, complete }) });
  }

  launchTask(key: string, amount?: number, source?: string): Observable<{ message: string }> {
    return this.http.post<any>(this.url('/admin/tasks'), { key, amount, source });
  }

  deleteTask(guid: string): Observable<{ message: string }> {
    return this.http.delete<any>(this.url(`/admin/tasks/${guid}`));
  }

  getStatistics(): Observable<{ items: Stat[] }> {
    return this.http.get<any>(this.url('/admin/statistics'));
  }

  // ── Media ─────────────────────────────────────────────────────────────

  getFileUrl(fileId: number): string {
    return `${this.base}/media/files/${fileId}`;
  }

  getImageMeta(guid: string): Observable<ImageMeta> {
    return this.http.get<ImageMeta>(this.url(`/media/images/${guid}`));
  }

  rotateImage(guid: string, degree: number): Observable<{ message: string }> {
    return this.http.post<any>(this.url(`/media/images/${guid}/rotate`), { degree });
  }

  // ── Helpers ─────────────────────────────────────────────────────────────

  private euHeaders(euGuid?: string): HttpHeaders {
    return euGuid ? new HttpHeaders({ 'X-EventUser-GUID': euGuid }) : new HttpHeaders();
  }
}
