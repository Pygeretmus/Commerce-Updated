export type Money = string; // always a decimal string such as "12.50": the client never does arithmetic on money

export type ListingStatus = "draft" | "active" | "ended" | "cancelled";
export type BidStatus = "winning" | "outbid" | "won" | "lost";

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Account {
  id: number;
  username: string;
  email: string;
}

export interface ListingListItem {
  id: number;
  title: string;
  starting_price: Money;
  current_price: Money;
  bids_count: number;
  status: ListingStatus;
  is_ended: boolean;
  sold: boolean | null;
  published_at: string | null;
  ends_at: string | null;
  category: { name: string; slug: string };
  seller: string | null;
  cover: string | null;
}

export interface MyListingItem extends ListingListItem {
  reserve_price: Money | null;
  closed_at: string | null;
  created_at: string;
  winner: string | null;
}

export interface MyBidItem extends ListingListItem {
  my_highest_bid: Money;
  my_status: BidStatus;
}

export interface ListingImage {
  id: number;
  url: string;
  thumbnail: string | null;
  position: number;
}

export interface ListingDetail {
  id: number;
  title: string;
  description: string;
  starting_price: Money;
  reserve_price?: Money | null;
  has_reserve: boolean;
  reserve_met: boolean | null;
  current_price: Money;
  bids_count: number;
  next_min_bid: Money;
  leader: string | null;
  winner: string | null;
  status: ListingStatus;
  is_ended: boolean;
  sold: boolean | null;
  published_at: string | null;
  ends_at: string | null;
  closed_at: string | null;
  seconds_left: number | null;
  server_time: string;
  created_at: string;
  category: { name: string; slug: string };
  seller: string | null;
  images: ListingImage[];
  is_seller: boolean;
  is_watching: boolean;
  my_bid_status: BidStatus | null;
}

export interface Bid {
  id: number;
  bidder: string | null;
  amount: Money;
  created_at: string;
  is_mine: boolean;
}

export interface ListingState {
  current_price: Money;
  bids_count: number;
  next_min_bid: Money;
  ends_at: string | null;
  leader: string | null;
  server_time: string;
}

export interface PlacedBid {
  bid: Bid;
  state: ListingState;
}

export interface Comment {
  id: number;
  author: string | null;
  body: string;
  created_at: string;
  is_seller: boolean;
  is_mine: boolean;
}

export type NotificationKind =
  | "outbid"
  | "won"
  | "sold"
  | "lost"
  | "ending_soon"
  | "new_comment"
  | "listing_ended"
  | "cancelled";

export interface AppNotification {
  id: number;
  kind: NotificationKind;
  text: string;
  listing: { id: number; title: string };
  data: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
}

export interface Summary {
  bids: Record<BidStatus, number>;
  listings: Record<ListingStatus, number>;
  watching: number;
  unread_notifications: number;
}

// Live events from the WebSocket
export type ListingEvent =
  | ({ type: "price_update"; listing_id: number } & ListingState)
  | {
      type: "listing_ended";
      listing_id: number;
      status: ListingStatus;
      sold: boolean;
      final_price: Money;
      winner: string | null;
      closed_at: string | null;
      server_time: string;
    }
  | { type: "hello"; server_time: string };

export type UserEvent =
  | ({ type: "notification" } & AppNotification)
  | { type: "hello"; server_time: string };
