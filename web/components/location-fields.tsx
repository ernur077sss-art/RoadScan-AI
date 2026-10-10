"use client";
import dynamic from "next/dynamic";
import { LocateFixed, MapPin } from "lucide-react";
import { useState } from "react";
import { ErrorBox, Spinner } from "./ui";
import { CoordinateInput } from "./coordinate-input";
import type { Point } from "@/lib/api";
const RoadMap = dynamic(() => import("./map"), {
  ssr: false,
  loading: () => <div className="map skeleton" />,
});
export function LocationFields({
  point,
  address,
  onPoint,
  onAddress,
}: {
  point: Point;
  address: string;
  onPoint: (
    p: Point,
    source: "gps" | "manual" | "unknown",
    accuracy?: number,
  ) => void;
  onAddress: (v: string) => void;
}) {
  const [locating, setLocating] = useState(false),
    [error, setError] = useState("");
  function locate() {
    setError("");
    if (!navigator.geolocation) {
      setError("Геолокация недоступна. Укажите место вручную.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        onPoint(
          { latitude: p.coords.latitude, longitude: p.coords.longitude },
          "gps",
          p.coords.accuracy,
        );
        setLocating(false);
      },
      () => {
        setError(
          "Не удалось определить местоположение. Отметьте точку на карте или опишите место.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }
  return (
    <div className="location-fields">
      <div className="field-heading">
        <h3>
          <MapPin size={20} />
          Место проблемы
        </h3>
        <button
          type="button"
          className="button secondary small"
          onClick={locate}
          disabled={locating}
        >
          {locating ? <Spinner /> : <LocateFixed size={17} />}Моя геопозиция
        </button>
      </div>
      <p className="muted">
        Нажмите на карту в месте дефекта. Позиция телефона может отличаться от
        места проблемы.
      </p>
      <RoadMap point={point} onChange={(p) => onPoint(p, "manual")} />
      <ErrorBox message={error} />
      <label htmlFor="address">
        Улица и ориентир <span aria-hidden>*</span>
      </label>
      <input
        id="address"
        value={address}
        maxLength={500}
        minLength={3}
        required
        onChange={(e) => onAddress(e.target.value)}
        placeholder="Например: улица Абая, у остановки"
        autoComplete="street-address"
      />
      <details className="coordinate-details">
        <summary>Указать координаты вручную</summary>
        <div className="two-fields">
          <div>
            <label htmlFor="latitude">Широта</label>
            <CoordinateInput
              id="latitude"
              value={point.latitude}
              onChange={(latitude) =>
                onPoint({ latitude, longitude: point.longitude }, "manual")
              }
            />
          </div>
          <div>
            <label htmlFor="longitude">Долгота</label>
            <CoordinateInput
              id="longitude"
              value={point.longitude}
              onChange={(longitude) =>
                onPoint({ latitude: point.latitude, longitude }, "manual")
              }
            />
          </div>
        </div>
      </details>
      {point.latitude != null && point.longitude != null ? (
        <div className="location-summary">
          <MapPin size={15} />
          {point.latitude.toFixed(5)}, {point.longitude.toFixed(5)}
          <button
            type="button"
            className="text-button"
            onClick={() =>
              onPoint({ latitude: null, longitude: null }, "unknown")
            }
          >
            Убрать точку
          </button>
        </div>
      ) : (
        <p className="hint">
          Без точки обращение получит отметку «Требуется уточнение места».
          Инспектор сможет запросить ориентиры.
        </p>
      )}
    </div>
  );
}
