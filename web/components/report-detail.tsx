"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  ArrowLeft,
  MapPin,
  CheckCircle,
  MessageCircle,
  Clock,
  Link2,
  ShieldCheck,
} from "lucide-react";
import {
  api,
  categories,
  date,
  type Report,
  type Point,
  type Incident,
} from "@/lib/api";
import { AuthGate, ErrorBox, Loading, Status, Spinner } from "./ui";
import { LocationFields } from "./location-fields";
import { CoordinateInput } from "./coordinate-input";
const RoadMap = dynamic(() => import("./map"), {
  ssr: false,
  loading: () => <div className="map skeleton" />,
});
export function ReportDetail({
  id,
  inspector = false,
}: {
  id: string;
  inspector?: boolean;
}) {
  return (
    <AuthGate inspector={inspector}>
      <Detail id={id} inspector={inspector} />
    </AuthGate>
  );
}
function Detail({ id, inspector }: { id: string; inspector: boolean }) {
  const [row, setRow] = useState<Report | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRow(await api<Report>("/reports/" + id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  async function updated(message: string) {
    setSuccess(message);
    await load();
  }
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} retry={() => void load()} />;
  if (!row) return null;
  const point = row.incident || row;
  return (
    <>
      <Link className="back-link" href={inspector ? "/inspector" : "/reports"}>
        <ArrowLeft size={17} />
        {inspector ? "К очереди инспектора" : "Мои обращения"}
      </Link>
      <div className="page-heading heading-row">
        <div>
          <div className="eyebrow">
            {row.number} · {date(row.received_at)}
          </div>
          <h1>{categories[row.category]}</h1>
          <p>
            <MapPin size={18} />
            {row.address}
          </p>
        </div>
        <Status status={row.status} />
      </div>
      {success && (
        <div className="success-message" role="status">
          <CheckCircle size={20} />
          {success}
        </div>
      )}
      <div className="detail-layout">
        <div className="detail-main">
          <section className="content-card">
            <h2>Что сообщил житель</h2>
            <p className="report-full-description">{row.description}</p>
            <div className="evidence-grid">
              {row.media.map((m) => (
                <div key={m.id}>
                  {m.kind === "image" ? (
                    <a href={m.url} target="_blank" rel="noreferrer">
                      <img
                        src={m.url}
                        alt="Фото дорожного дефекта, приложенное к обращению"
                        loading="lazy"
                      />
                    </a>
                  ) : (
                    <video src={m.url} controls preload="metadata" />
                  )}
                </div>
              ))}
            </div>
          </section>
          <section className="content-card">
            <div className="field-heading">
              <h2>Местоположение</h2>
              <span className="location-tag">
                {row.incident?.location_verified
                  ? "Проверено инспектором"
                  : point.latitude != null
                    ? "Требует проверки"
                    : "Требует уточнения"}
              </span>
            </div>
            <RoadMap point={point} />
            <p className="hint">
              {point.latitude != null && point.longitude != null
                ? `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`
                : "Точка пока не указана. На карте показан центр Семея."}
            </p>
            {row.incident_id && (
              <p className="hint">
                <Link2 size={14} />
                Карточка дефекта: {row.incident_id.slice(0, 8).toUpperCase()}
              </p>
            )}
          </section>
          {row.response && (
            <section className="content-card response-card">
              <div className="card-icon-title">
                <MessageCircle size={22} />
                <h2>Ответ инспектора</h2>
              </div>
              <p>{row.response}</p>
              {row.status === "confirmed" && (
                <p className="hint">
                  Проблема подтверждена. Этот статус не означает, что ремонт
                  выполнен.
                </p>
              )}
            </section>
          )}
          {!inspector && row.status === "needs_info" && (
            <Clarify row={row} updated={updated} />
          )}
          <section className="content-card">
            <h2>История обращения</h2>
            <ol className="timeline">
              {row.history?.map((event, i) => (
                <li key={i}>
                  <span className="timeline-dot" />
                  <div>
                    <time>{date(event.created_at)}</time>
                    <p>{event.note}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
        <aside className="detail-aside">
          {inspector ? (
            <Moderation
              key={row.version + ":" + row.incident?.version}
              row={row}
              updated={updated}
            />
          ) : (
            <div className="content-card">
              <ShieldCheck size={26} />
              <h3>Обращение сохранено</h3>
              <p className="muted">
                Решения и уточнения инспектора появятся на этой странице.
              </p>
              <Link href="/reports/new" className="button secondary full">
                Сообщить о другой проблеме
              </Link>
            </div>
          )}
          <div className="integration-card">
            <h3>Передача в 109</h3>
            <p>
              {!row.integration
                ? "109 пока не подключён. Обращение находится в базе инспектора."
                : row.integration.status === "simulated"
                  ? "Проверена демонстрационная передача. Реальная заявка в 109 не отправлялась."
                  : row.integration.status === "queued"
                    ? "Ожидает обработки демонстрационной очередью."
                    : "Передача не выполнена."}
            </p>
            {row.integration?.external_id && (
              <code>{row.integration.external_id}</code>
            )}
            {row.integration?.last_error && (
              <p className="hint">{row.integration.last_error}</p>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
function Clarify({
  row,
  updated,
}: {
  row: Report;
  updated: (message: string) => Promise<void>;
}) {
  const [note, setNote] = useState(""),
    [address, setAddress] = useState(row.address),
    [point, setPoint] = useState<Point>({
      latitude: row.latitude,
      longitude: row.longitude,
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/reports/" + row.id + "/clarify", {
        method: "POST",
        body: JSON.stringify({ version: row.version, note, address, ...point }),
      });
      await updated("Уточнение отправлено инспектору.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="content-card">
      <h2>Помогите уточнить проблему</h2>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend className="sr-only">Уточнение обращения</legend>
          <label htmlFor="clarification">Ваше уточнение</label>
          <textarea
            id="clarification"
            minLength={3}
            maxLength={3000}
            required
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
          />
          <LocationFields
            point={point}
            address={address}
            onAddress={setAddress}
            onPoint={(p) => setPoint(p)}
          />
        </fieldset>
        <ErrorBox message={error} />
        <button className="button" disabled={busy}>
          {busy ? <Spinner /> : null}Отправить уточнение
        </button>
      </form>
    </section>
  );
}
function Moderation({
  row,
  updated,
}: {
  row: Report;
  updated: (message: string) => Promise<void>;
}) {
  const [status, setStatus] = useState("confirmed"),
    [note, setNote] = useState(""),
    [point, setPoint] = useState<Point>({
      latitude: row.incident ? row.incident.latitude : row.latitude,
      longitude: row.incident ? row.incident.longitude : row.longitude,
    }),
    [verified, setVerified] = useState(
      row.incident?.location_verified ?? false,
    ),
    [target, setTarget] = useState(row.incident_id || ""),
    [candidates, setCandidates] = useState<Incident[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    api<Incident[]>("/inspector/incidents?category=" + row.category)
      .then(setCandidates)
      .catch((e) => setError(e.message));
  }, [row.category]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/inspector/reports/" + row.id + "/decision", {
        method: "POST",
        body: JSON.stringify({
          version: row.version,
          status,
          note,
          latitude: status === "confirmed" && !target ? point.latitude : null,
          longitude: status === "confirmed" && !target ? point.longitude : null,
          location_verified:
            status === "confirmed" && !target ? verified : false,
          incident_id: status === "confirmed" && target ? target : null,
        }),
      });
      await updated("Решение сохранено. Житель увидит ответ в своём кабинете.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function location() {
    if (!row.incident) return;
    if (note.trim().length < 3) {
      setError("Напишите причину уточнения местоположения.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/inspector/incidents/" + row.incident.id + "/location", {
        method: "POST",
        body: JSON.stringify({
          version: row.incident.version,
          ...point,
          location_verified: verified,
          note,
        }),
      });
      await updated("Местоположение дефекта уточнено с сохранением истории.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="content-card moderation-card">
      <div className="eyebrow">ПРОВЕРКА ОБРАЩЕНИЯ</div>
      <h2>Решение инспектора</h2>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <legend className="sr-only">Решение инспектора</legend>
          <label htmlFor="decision-status">Результат проверки</label>
          <select
            id="decision-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="confirmed">Подтвердить дефект</option>
            <option value="needs_info">Запросить уточнение</option>
            <option value="rejected">Отклонить с причиной</option>
          </select>
          {status === "confirmed" && (
            <>
              <label htmlFor="link-incident">Карточка дефекта</label>
              <select
                id="link-incident"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Создать отдельный дефект</option>
                {row.incident_id &&
                  !candidates.some((c) => c.id === row.incident_id) && (
                    <option value={row.incident_id}>
                      Текущий дефект · {row.incident_id.slice(0, 8)}
                    </option>
                  )}
                {candidates.map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.id === row.incident_id ? "Текущий · " : ""}
                    {c.id.slice(0, 8).toUpperCase()} ·{" "}
                    {c.latitude != null
                      ? `${c.latitude.toFixed(4)}, ${c.longitude?.toFixed(4)}`
                      : "место не уточнено"}
                  </option>
                ))}
              </select>
              {target && <CandidatePreview id={target} />}
              <p className="hint">
                Выбирайте существующий дефект только после сравнения места и
                материалов. Радиус сам по себе не доказывает совпадение.
              </p>
              {(!target || target === row.incident_id) && (
                <>
                  <div className="two-fields">
                    <div>
                      <label htmlFor="decision-lat">Широта</label>
                      <CoordinateInput
                        id="decision-lat"
                        value={point.latitude}
                        onChange={(latitude) =>
                          setPoint((p) => ({ ...p, latitude }))
                        }
                      />
                    </div>
                    <div>
                      <label htmlFor="decision-lng">Долгота</label>
                      <CoordinateInput
                        id="decision-lng"
                        value={point.longitude}
                        onChange={(longitude) =>
                          setPoint((p) => ({ ...p, longitude }))
                        }
                      />
                    </div>
                  </div>
                  <label className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={verified}
                      onChange={(e) => setVerified(e.target.checked)}
                      disabled={
                        point.latitude == null || point.longitude == null
                      }
                    />
                    <span>Место дефекта проверено</span>
                  </label>
                  {target && (
                    <p className="hint">
                      Изменение точки текущего дефекта сохраняется отдельной
                      кнопкой ниже.
                    </p>
                  )}
                </>
              )}
            </>
          )}
          <label htmlFor="decision-note">
            Ответ жителю / причина изменения
          </label>
          <textarea
            id="decision-note"
            minLength={3}
            maxLength={3000}
            rows={4}
            required
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Что установлено и что будет дальше"
          />
        </fieldset>
        <ErrorBox message={error} />
        <button className="button full" disabled={busy}>
          {busy ? <Spinner /> : <CheckCircle size={18} />}Сохранить решение
        </button>
        {row.incident &&
          target === row.incident_id &&
          status === "confirmed" && (
            <button
              className="button secondary full"
              type="button"
              onClick={() => void location()}
              disabled={busy}
            >
              Уточнить точку текущего дефекта
            </button>
          )}
      </form>
    </section>
  );
}

function CandidatePreview({ id }: { id: string }) {
  const [rows, setRows] = useState<Report[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<Report[]>("/inspector/incidents/" + id + "/observations")
      .then((data) => {
        if (active) setRows(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);
  return (
    <div className="candidate-preview">
      <strong>Материалы выбранного дефекта</strong>
      {loading ? (
        <Loading />
      ) : (
        <>
          {rows.map((r) => (
            <Link
              key={r.id}
              href={"/inspector/reports/" + r.id}
              target="_blank"
              rel="noreferrer"
            >
              {r.number} · {r.address} — открыть фото и описание
            </Link>
          ))}
        </>
      )}
      <ErrorBox message={error} />
    </div>
  );
}
