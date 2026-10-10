export type User = {
  id: string;
  phone: string;
  role: "citizen" | "inspector" | "admin";
};
export type Health = {
  environment: string;
  sms: string;
  integration_109: string;
  database: string;
};
export type Media = {
  id: string;
  kind: "image" | "video";
  url: string;
  size?: number;
};
export type Point = { latitude: number | null; longitude: number | null };
export type Incident = Point & {
  id: string;
  category?: string;
  location_verified: boolean;
  first_received_at: number;
  version: number;
};
export type Report = Point & {
  id: string;
  number: string;
  category: string;
  description: string;
  address: string;
  location_source: string;
  status: string;
  received_at: number;
  updated_at: number;
  version: number;
  response: string;
  incident_id: string | null;
  incident: Incident | null;
  media: Media[];
  history?: { action: string; note: string; created_at: number }[];
  integration: {
    status: string;
    external_id: string | null;
    attempts: number;
    last_error: string | null;
  } | null;
};
export const categories: Record<string, string> = {
  pothole: "Яма на дороге",
  surface: "Разрушение покрытия",
  manhole: "Повреждённый люк",
  other: "Другая проблема",
};
export const statuses: Record<string, string> = {
  pending: "На проверке",
  needs_info: "Нужно уточнение",
  confirmed: "Подтверждено",
  rejected: "Отклонено",
};
export function date(value: number) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Almaty",
  }).format(new Date(value * 1000));
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-RoadScan-Request", "1");
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Нет связи с сервером. Проверьте интернет и повторите попытку.",
      0,
    );
  }
  const data = await response.json().catch(() => ({
    detail: "Сервис временно недоступен. Попробуйте ещё раз.",
  }));
  if (!response.ok)
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : "Проверьте заполнение полей",
      response.status,
    );
  return data as T;
}
