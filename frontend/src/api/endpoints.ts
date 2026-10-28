import { api, saveTokens } from "./client";
import type {
  Account,
  AppNotification,
  Bid,
  Category,
  Comment,
  ListingDetail,
  ListingImage,
  ListingListItem,
  MyBidItem,
  MyListingItem,
  Paginated,
  PlacedBid,
  Summary,
} from "./types";

export interface ListingQuery {
  q?: string;
  category?: string;
  status?: "active" | "ended";
  min_price?: string;
  max_price?: string;
  seller?: string;
  watching?: boolean;
  bidding?: boolean;
  ordering?: string;
  page?: number;
}

export interface ListingInput {
  title: string;
  description: string;
  category: number;
  starting_price: string;
  reserve_price: string | null;
}

export const accountApi = {
  async login(username: string, password: string): Promise<void> {
    const tokens = await api<{ access: string; refresh: string }>("/token/", {
      method: "POST",
      body: { username, password },
      anonymous: true,
    });
    saveTokens(tokens);
  },
  register: (username: string, email: string, password: string) =>
    api<Account>("/accounts/", {
      method: "POST",
      body: { username, email, password },
      anonymous: true,
    }),
  me: () => api<Account>("/accounts/me/"),
  update: (data: {
    username?: string;
    email?: string;
    current_password: string;
  }) => api<Account>("/accounts/me/", { method: "PATCH", body: data }),
  changePassword: (current_password: string, new_password: string) =>
    api<{ detail: string }>("/accounts/password/", {
      method: "PUT",
      body: { current_password, new_password },
    }),
  destroy: (current_password: string) =>
    api<void>("/accounts/destroy/", {
      method: "POST",
      body: { current_password },
    }),
};

export const catalogApi = {
  categories: () => api<Category[]>("/categories/"),
  list: (query: ListingQuery, signal?: AbortSignal) =>
    api<Paginated<ListingListItem>>("/listings/", {
      query: { ...query },
      signal,
    }),
  get: (id: number | string, signal?: AbortSignal) =>
    api<ListingDetail>(`/listings/${id}/`, { signal }),
};

export const sellerApi = {
  create: (data: ListingInput) =>
    api<ListingDetail>("/listings/", { method: "POST", body: data }),
  update: (id: number, data: Partial<ListingInput>) =>
    api<ListingDetail>(`/listings/${id}/`, { method: "PATCH", body: data }),
  remove: (id: number) => api<void>(`/listings/${id}/`, { method: "DELETE" }),
  publish: (id: number, duration_days: number) =>
    api<ListingDetail>(`/listings/${id}/publish/`, {
      method: "POST",
      body: { duration_days },
    }),
  cancel: (id: number) =>
    api<ListingDetail>(`/listings/${id}/cancel/`, { method: "POST" }),
  endNow: (id: number) =>
    api<ListingDetail>(`/listings/${id}/end_now/`, { method: "POST" }),
  uploadImage: (id: number, file: File) => {
    const form = new FormData();
    form.append("image", file);
    return api<ListingImage>(`/listings/${id}/images/`, {
      method: "POST",
      body: form,
    });
  },
  removeImage: (id: number, imageId: number) =>
    api<void>(`/listings/${id}/images/${imageId}/`, { method: "DELETE" }),
  orderImages: (id: number, ids: number[]) =>
    api<ListingImage[]>(`/listings/${id}/images/order/`, {
      method: "PUT",
      body: { ids },
    }),
};

export const biddingApi = {
  history: (id: number, page = 1, signal?: AbortSignal) =>
    api<Paginated<Bid>>(`/listings/${id}/bids/`, { query: { page }, signal }),
  place: (id: number, amount: string) =>
    api<PlacedBid>(`/listings/${id}/bids/`, {
      method: "POST",
      body: { amount },
    }),
};

export const discussionApi = {
  comments: (id: number, page = 1, signal?: AbortSignal) =>
    api<Paginated<Comment>>(`/listings/${id}/comments/`, {
      query: { page },
      signal,
    }),
  post: (id: number, body: string) =>
    api<Comment>(`/listings/${id}/comments/`, {
      method: "POST",
      body: { body },
    }),
  remove: (commentId: number) =>
    api<void>(`/comments/${commentId}/`, { method: "DELETE" }),
  watch: (id: number) => api<void>(`/listings/${id}/watch/`, { method: "PUT" }),
  unwatch: (id: number) =>
    api<void>(`/listings/${id}/watch/`, { method: "DELETE" }),
};

export const meApi = {
  summary: (signal?: AbortSignal) => api<Summary>("/me/summary/", { signal }),
  bids: (status: string | undefined, page: number, signal?: AbortSignal) =>
    api<Paginated<MyBidItem>>("/me/bids/", { query: { status, page }, signal }),
  listings: (status: string | undefined, page: number, signal?: AbortSignal) =>
    api<Paginated<MyListingItem>>("/me/listings/", {
      query: { status, page },
      signal,
    }),
  notifications: (page: number, signal?: AbortSignal) =>
    api<Paginated<AppNotification>>("/notifications/", {
      query: { page },
      signal,
    }),
  markRead: (body: { ids?: number[]; all?: boolean }) =>
    api<{ updated: number }>("/notifications/read/", { method: "POST", body }),
  wsTicket: () =>
    api<{ ticket: string; expires_in: number }>("/ws/ticket/", {
      method: "POST",
    }),
};
