"use client";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowUpRight,
  Plus,
  MapPin,
  Search,
  RefreshCw,
  CheckCircle,
  Clock,
  Map as MapIcon,
  ListFilter,
} from "lucide-react";
import { api, categories, statuses, date, type Report } from "@/lib/api";
import { AuthGate, Empty, ErrorBox, Loading, Status } from "./ui";
const RoadMap = dynamic(() => import("./map"), {
  ssr: false,
  loading: () => <div className="map skeleton" />,
});
type Metrics = {
  incidents: number;
  verified: number;
  unverified: number;
  geolocation_percent: number | null;
  pending_all_time: number;
  target: number;
};
export function ReportList({ inspector = false }: { inspector?: boolean }) {
  return (
    <AuthGate inspector={inspector}>
      <List inspector={inspector} />
    </AuthGate>
  );
}
function List({ inspector }: { inspector: boolean }) {
  const params = useSearchParams(),
    router = useRouter(),
    [rows, setRows] = useState<Report[]>([]),
    [metrics, setMetrics] = useState<Metrics | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [mapView, setMapView] = useState(false),
    [hasMore, setHasMore] = useState(false),
    [offset, setOffset] = useState(0),
    [moreBusy, setMoreBusy] = useState(false);
  const status = params.get("status") || "",
    category = params.get("category") || "",
    q = params.get("q") || "",
    dateFrom = params.get("from") || "",
    dateTo = params.get("to") || "";
  const requestVersion = useRef(0);
  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError("");
    setMetrics(null);
    try {
      const query = new URLSearchParams({ status, category, q });
      const range = new URLSearchParams();
      if (dateFrom)
        range.set(
          "date_from",
          String(
            Math.floor(new Date(dateFrom + "T00:00:00+05:00").getTime() / 1000),
          ),
        );
      if (dateTo)
        range.set(
          "date_to",
          String(
            Math.floor(new Date(dateTo + "T00:00:00+05:00").getTime() / 1000) +
              86400,
          ),
        );
      const [data, kpi] = await Promise.all([
        api<Report[]>((inspector ? "/inspector" : "") + "/reports?" + query),
        inspector
          ? api<Metrics>("/inspector/metrics?" + range)
          : Promise.resolve(null),
      ]);
      if (version !== requestVersion.current) return;
      setRows(data);
      setOffset(0);
      setHasMore(data.length === 50);
      setMetrics(kpi);
    } catch (e) {
      if (version === requestVersion.current) setError((e as Error).message);
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [status, category, q, inspector, dateFrom, dateTo]);
  useEffect(() => {
    void load();
    return () => {
      requestVersion.current++;
    };
  }, [load]);
  function filter(k: string, v: string) {
    const search = new URLSearchParams(params);
    if (v) search.set(k, v);
    else search.delete(k);
    router.replace((inspector ? "/inspector" : "/reports") + "?" + search);
  }
  async function more() {
    const version = requestVersion.current;
    setMoreBusy(true);
    try {
      const next = offset + 50;
      const result = await api<Report[]>(
        (inspector ? "/inspector" : "") +
          "/reports?" +
          new URLSearchParams({ status, category, q, offset: String(next) }),
      );
      if (version !== requestVersion.current) return;
      setRows((prev) => [...prev, ...result]);
      setOffset(next);
      setHasMore(result.length === 50);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setMoreBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading heading-row">
        <div>
          <div className="eyebrow">
            {inspector ? "РАБОЧЕЕ МЕСТО ИНСПЕКТОРА" : "ВАША СВЯЗЬ С ГОРОДОМ"}
          </div>
          <h1>{inspector ? "Внимание к каждой дороге" : "Мои обращения"}</h1>
          <p>
            {inspector
              ? "Проверяйте сообщения жителей и уточняйте места дефектов."
              : "Здесь сохраняются ваши сообщения и ответы инспектора."}
          </p>
        </div>
        {!inspector && (
          <Link href="/reports/new" className="button">
            <Plus size={18} />
            Новое обращение
          </Link>
        )}
      </div>
      {inspector && (
        <section className="metrics-section" aria-label="Показатели реестра">
          <div className="metrics-grid">
            <div className="metric-card">
              <Clock size={20} />
              <span>Ожидают проверки</span>
              <strong>{metrics?.pending_all_time ?? "—"}</strong>
              <small>Все поступившие обращения</small>
            </div>
            <div className="metric-card">
              <MapPin size={20} />
              <span>Уникальные дефекты</span>
              <strong>{metrics?.incidents ?? "—"}</strong>
              <small>Подтверждённые, без дублей</small>
            </div>
            <div className="metric-card featured">
              <CheckCircle size={20} />
              <span>Проверенная геопривязка</span>
              <strong>
                {metrics?.geolocation_percent != null
                  ? `${metrics.geolocation_percent}%`
                  : "Нет данных"}
              </strong>
              <small>
                Цель ≥90% ·{" "}
                {metrics ? `${metrics.verified} из ${metrics.incidents}` : "—"}
              </small>
            </div>
          </div>
          <div className="metric-period">
            <span>Период создания дефектов для KPI:</span>
            <label>
              С{" "}
              <input
                aria-label="KPI с даты"
                type="date"
                value={dateFrom}
                onChange={(e) => filter("from", e.target.value)}
              />
            </label>
            <label>
              По{" "}
              <input
                aria-label="KPI по дату"
                type="date"
                value={dateTo}
                onChange={(e) => filter("to", e.target.value)}
              />
            </label>
          </div>
          <p className="hint">
            KPI считается по уникальным дефектам, включая объекты без точки.
            Фильтры очереди ниже не изменяют знаменатель KPI.
          </p>
        </section>
      )}
      <section className="reports-section">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={18} />
            <input
              aria-label="Поиск по адресу"
              type="search"
              key={q}
              defaultValue={q}
              placeholder="Улица или ориентир"
              onKeyDown={(e) => {
                if (e.key === "Enter") filter("q", e.currentTarget.value);
              }}
              onBlur={(e) => {
                if (e.target.value !== q) filter("q", e.target.value);
              }}
            />
          </div>
          <select
            aria-label="Статус обращения"
            value={status}
            onChange={(e) => filter("status", e.target.value)}
          >
            <option value="">Все статусы</option>
            {Object.entries(statuses).map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </select>
          <select
            aria-label="Категория"
            value={category}
            onChange={(e) => filter("category", e.target.value)}
          >
            <option value="">Все проблемы</option>
            {Object.entries(categories).map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </select>
          <button
            className="icon-button"
            onClick={() => setMapView(!mapView)}
            aria-label={mapView ? "Показать список" : "Показать карту"}
            aria-pressed={mapView}
          >
            {mapView ? <ListFilter size={20} /> : <MapIcon size={20} />}
          </button>
          <button
            className="icon-button"
            onClick={() => void load()}
            aria-label="Обновить обращения"
          >
            <RefreshCw size={18} />
          </button>
        </div>
        <ErrorBox message={error} retry={() => void load()} />
        {loading ? (
          <Loading />
        ) : !rows.length ? (
          <Empty
            title={
              status || category || q
                ? "Ничего не найдено"
                : "Обращений пока нет"
            }
            text={
              status || category || q
                ? "Попробуйте изменить фильтры."
                : inspector
                  ? "Новые сообщения жителей появятся здесь."
                  : "Начните с проблемы, которую заметили на своей улице."
            }
            action={!inspector && !status && !category && !q}
          />
        ) : (
          <>
            {mapView && (
              <>
                <RoadMap
                  pins={rows.map((r) => ({
                    latitude: r.incident ? r.incident.latitude : r.latitude,
                    longitude: r.incident ? r.incident.longitude : r.longitude,
                    label: r.number + " · " + categories[r.category],
                    href: (inspector ? "/inspector" : "") + "/reports/" + r.id,
                  }))}
                />
                <p className="hint">
                  Показаны загруженные обращения с точкой. Отсутствие маркера не
                  означает отсутствие дефекта.
                </p>
              </>
            )}
            <div className="report-grid">
              {rows.map((row) => (
                <Link
                  href={(inspector ? "/inspector" : "") + "/reports/" + row.id}
                  key={row.id}
                  className="report-card"
                >
                  <div className="report-card-top">
                    <Status status={row.status} />
                    <ArrowUpRight size={20} />
                  </div>
                  <h2>{categories[row.category]}</h2>
                  <p className="report-description">{row.description}</p>
                  <div className="report-address">
                    <MapPin size={16} />
                    {row.address}
                  </div>
                  <div className="report-card-bottom">
                    <span>{row.number}</span>
                    <time>{date(row.received_at)}</time>
                  </div>
                </Link>
              ))}
            </div>
            {hasMore && (
              <button
                className="button secondary load-more"
                onClick={() => void more()}
                disabled={moreBusy}
              >
                {moreBusy ? "Загрузка…" : "Показать ещё"}
              </button>
            )}
          </>
        )}
      </section>
    </>
  );
}
