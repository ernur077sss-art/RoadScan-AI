import { get, set, del } from "idb-keyval";
import type { Point } from "./api";
export type DraftFile = {
  key: string;
  file: File;
  mediaId?: string;
  kind?: "image" | "video";
};
export type Draft = Point & {
  event_id: string;
  category: string;
  description: string;
  address: string;
  location_source: "unknown" | "manual" | "gps";
  device_accuracy: number | null;
  files: DraftFile[];
  saved_at: number;
  step: number;
  pendingPayload?: {
    event_id: string;
    category: string;
    description: string;
    address: string;
    latitude: number | null;
    longitude: number | null;
    location_source: string;
    device_accuracy: number | null;
    media_ids: (string | undefined)[];
  };
};
export function emptyDraft(): Draft {
  return {
    event_id: crypto.randomUUID(),
    category: "pothole",
    description: "",
    address: "",
    latitude: null,
    longitude: null,
    location_source: "unknown",
    device_accuracy: null,
    files: [],
    saved_at: Date.now(),
    step: 0,
  };
}
export async function loadDraft(userId: string) {
  return get<Draft>("roadscan-draft:" + userId);
}
export async function saveDraft(userId: string, draft: Draft) {
  await set("roadscan-draft:" + userId, { ...draft, saved_at: Date.now() });
}
export async function clearDraft(userId: string) {
  await del("roadscan-draft:" + userId);
}
