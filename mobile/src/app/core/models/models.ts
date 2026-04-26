// Core TypeScript models matching the Flask REST API contracts

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

// Legacy users namespace pagination
export interface UserCollection {
  items: User[];
  _meta: { page: number; per_page: number; total_pages: number; total_items: number };
  _links: { self: string; next: string; prev: string };
}

export interface TokenResponse {
  token: string;
}

export interface AuthResult {
  token: string;
  user_guid: string;
  username: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  last_seen?: string;
  about_me?: string;
  post_count?: number;
  is_admin?: boolean;
  _links?: { self: string; avatar: string };
}

export interface Currency {
  id: number;
  guid: string;
  code: string;
  name: string;
  number: number;
  exponent: number;
  inCHF: number;
  description?: string;
}

export interface Event {
  guid: string;
  name: string;
  date: string;
  closed: boolean;
  description?: string;
  fileshare_link?: string;
  exchange_fee: number;
  base_currency_code: string;
  admin_username: string;
  accountant_username: string;
  stats?: { users: number; posts: number; expenses: number; settlements: number };
  image_url?: string;
}

export interface EventUser {
  guid: string;
  id: number;
  username: string;
  email: string;
  weighting: number;
  locale: string;
  about_me?: string;
  avatar?: string;
}

export interface EventCurrency {
  currency_code: string;
  currency_name: string;
  inCHF: number;
}

export interface Expense {
  guid: string;
  amount: number;
  amount_str: string;
  currency_code: string;
  date: string;
  description?: string;
  user_username: string;
  image_url?: string;
}

export interface Settlement {
  guid: string;
  amount: number;
  amount_str: string;
  currency_code: string;
  sender_username: string;
  recipient_username: string;
  draft: boolean;
  date: string;
  description?: string;
}

export interface Post {
  guid: string;
  body: string;
  timestamp: string;
  author_username: string;
}

export interface BalanceUser {
  username: string;
  paid: string;
  spent: string;
  sent: string;
  received: string;
  balance: string;
}

export interface Balance {
  balances: BalanceUser[];
  total_expenses: string;
  draft_settlements: Settlement[];
}

export interface Message {
  id: number;
  body: string;
  timestamp: string;
  sender: string;
  recipient: string;
}

export interface Notification {
  name: string;
  data: any;
  timestamp: number;
}

export interface Log {
  id: number;
  severity: string;
  module: string;
  msg_type: string;
  msg: string;
  date: string;
  username: string;
  trace?: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  complete: boolean;
  progress: number;
  username: string;
}

export interface Stat {
  label: string;
  count: number;
}

export interface ImageMeta {
  guid: string;
  url: string;
  width: number;
  height: number;
}
