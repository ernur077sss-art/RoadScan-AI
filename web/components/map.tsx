"use client";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { Point } from "@/lib/api";
type Pin = Point & { label?: string; href?: string };
const EMPTY_PINS: Pin[] = [];
function valid<T extends Point>(
  p?: T,
): p is T & { latitude: number; longitude: number } {
  return (
    p?.latitude != null &&
    p.longitude != null &&
    Number.isFinite(p.latitude) &&
    Number.isFinite(p.longitude) &&
    Math.abs(p.latitude) <= 90 &&
    Math.abs(p.longitude) <= 180
  );
}
export default function RoadMap({
  point,
  onChange,
  pins = EMPTY_PINS,
}: {
  point?: Point;
  onChange?: (p: Point) => void;
  pins?: Pin[];
}) {
  const node = useRef<HTMLDivElement>(null),
    map = useRef<LeafletMap | null>(null),
    callback = useRef(onChange);
  const [error, setError] = useState(""),
    [ready, setReady] = useState(false);
  const editable = !!onChange;
  useEffect(() => {
    callback.current = onChange;
  }, [onChange]);
  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    import("leaflet")
      .then((L) => {
        if (disposed || !node.current) return;
        const m = L.map(node.current, { scrollWheelZoom: false }).setView(
          [50.411, 80.249],
          13,
        );
        map.current = m;
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        })
          .on("tileerror", () =>
            setError(
              "Подложка карты недоступна. Можно указать координаты или описание места.",
            ),
          )
          .addTo(m);
        m.on("click", (e) =>
          callback.current?.({
            latitude: +e.latlng.lat.toFixed(6),
            longitude: +e.latlng.lng.toFixed(6),
          }),
        );
        const observer = new ResizeObserver(() => m.invalidateSize());
        observer.observe(node.current);
        cleanup = () => {
          observer.disconnect();
          m.remove();
          map.current = null;
        };
        setReady(true);
      })
      .catch(() =>
        setError("Карта недоступна. Укажите координаты или описание места."),
      );
    return () => {
      disposed = true;
      cleanup();
    };
  }, []);
  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    let cleanup = () => {};
    import("leaflet").then((L) => {
      if (disposed || !map.current || !valid(point)) return;
      const icon = L.divIcon({
        className: "map-pin-wrapper",
        html: '<span class="map-pin"></span>',
        iconSize: [28, 36],
        iconAnchor: [14, 36],
      });
      const marker = L.marker([point.latitude, point.longitude], {
        icon,
        draggable: editable,
        keyboard: true,
        title: "Место дефекта",
      }).addTo(map.current);
      marker.on("dragend", () => {
        const p = marker.getLatLng();
        callback.current?.({
          latitude: +p.lat.toFixed(6),
          longitude: +p.lng.toFixed(6),
        });
      });
      map.current.panTo([point.latitude, point.longitude]);
      cleanup = () => {
        marker.remove();
      };
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [ready, point?.latitude, point?.longitude, editable]);
  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    let cleanup = () => {};
    import("leaflet").then((L) => {
      if (disposed || !map.current) return;
      const layer = L.layerGroup().addTo(map.current);
      const positions: [number, number][] = [];
      pins.forEach((p) => {
        if (!valid(p)) return;
        const popup = document.createElement("div");
        if (p.href) {
          const a = document.createElement("a");
          a.href = p.href;
          a.textContent = p.label || "Открыть обращение";
          popup.append(a);
        } else popup.textContent = p.label || "Обращение";
        positions.push([p.latitude, p.longitude]);
        L.circleMarker([p.latitude, p.longitude], {
          radius: 8,
          color: "currentColor",
          className: "report-map-dot",
          fillOpacity: 1,
        })
          .bindPopup(popup)
          .addTo(layer);
      });
      if (positions.length)
        map.current.fitBounds(positions, { padding: [24, 24], maxZoom: 15 });
      cleanup = () => {
        layer.remove();
      };
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [ready, pins]);
  return (
    <div className="map-container">
      <div
        ref={node}
        className="map"
        aria-label={
          editable
            ? "Карта выбора места. Можно также ввести координаты ниже."
            : "Карта обращений"
        }
      />
      {error && (
        <p className="map-warning" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
