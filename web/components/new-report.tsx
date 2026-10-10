"use client";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Camera,
  Video,
  ImagePlus,
  X,
  ArrowLeft,
  ArrowRight,
  Check,
  Save,
  MapPin,
} from "lucide-react";
import { useAuth } from "./providers";
import { AuthGate, ErrorBox, Loading, Spinner } from "./ui";
import { LocationFields } from "./location-fields";
import { api, ApiError, categories, type Report, type Media } from "@/lib/api";
import {
  emptyDraft,
  loadDraft,
  saveDraft,
  clearDraft,
  type Draft,
  type DraftFile,
} from "@/lib/draft";

function FilePreview({
  item,
  onRemove,
}: {
  item: DraftFile;
  onRemove: () => void;
}) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const u = URL.createObjectURL(item.file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [item.file]);
  return (
    <div className="upload-preview">
      {item.file.type.startsWith("video/") ? (
        <video src={url || undefined} controls preload="metadata" />
      ) : (
        <img src={url || undefined} alt="Фотография для обращения" />
      )}
      <button
        type="button"
        className="remove-file"
        onClick={onRemove}
        aria-label={"Удалить " + item.file.name}
      >
        <X size={18} />
      </button>
      <small>{item.file.name}</small>
    </div>
  );
}
function Form() {
  const { user } = useAuth(),
    router = useRouter();
  const [draft, setDraft] = useState<Draft | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(""),
    [saved, setSaved] = useState(""),
    [restored, setRestored] = useState(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    if (user)
      loadDraft(user.id)
        .then((d) => {
          if (mounted.current) {
            setDraft(d || emptyDraft());
            setRestored(!!d);
          }
        })
        .catch(() => {
          setDraft(emptyDraft());
          setError(
            "Браузер не разрешил хранить черновик. Не закрывайте страницу до отправки.",
          );
        });
    return () => {
      mounted.current = false;
    };
  }, [user?.id]);
  useEffect(() => {
    if (!draft || !user || busy) return;
    const t = setTimeout(() => {
      saveDraft(user.id, draft)
        .then(() => setSaved("Черновик сохранён на этом устройстве"))
        .catch(() =>
          setSaved(
            "Не удалось сохранить черновик. Возможно, недостаточно места.",
          ),
        );
    }, 500);
    return () => clearTimeout(t);
  }, [draft, user, busy]);
  if (!draft || !user) return <Loading />;
  const d = draft;
  function update(patch: Partial<Draft>) {
    setDraft((prev) => (prev ? { ...prev, ...patch } : prev));
    setError("");
  }
  function addFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (d.files.length + files.length > 4) {
      setError("Можно прикрепить до 4 файлов.");
      return;
    }
    if (files.some((f) => f.size > 25 * 1024 * 1024)) {
      setError("Размер одного файла — до 25 MB.");
      return;
    }
    if (
      files.some(
        (f) =>
          ![
            "image/jpeg",
            "image/png",
            "image/webp",
            "video/mp4",
            "video/webm",
            "video/quicktime",
          ].includes(f.type),
      )
    ) {
      setError(
        "Используйте JPEG, PNG, WebP или видео MP4, WebM, MOV. Фото HEIC нужно преобразовать в JPEG.",
      );
      return;
    }
    update({
      files: [
        ...d.files,
        ...files.map((file) => ({ file, key: crypto.randomUUID() })),
      ],
    });
  }
  function next() {
    setError("");
    if (d.step === 0 && (!d.files.length || d.description.trim().length < 5)) {
      setError(
        "Добавьте хотя бы одно фото или видео и описание от 5 символов.",
      );
      return;
    }
    if (d.step === 1) {
      if (d.address.trim().length < 3) {
        setError("Укажите улицу или ориентир.");
        return;
      }
      if (
        (d.latitude == null) !== (d.longitude == null) ||
        (d.latitude != null &&
          (!Number.isFinite(d.latitude) || Math.abs(d.latitude) > 90)) ||
        (d.longitude != null &&
          (!Number.isFinite(d.longitude) || Math.abs(d.longitude) > 180))
      ) {
        setError(
          "Проверьте обе координаты: широта от −90 до 90, долгота от −180 до 180.",
        );
        return;
      }
    }
    update({ step: d.step + 1 });
  }
  async function submit() {
    if (!user) return;
    setBusy(true);
    setError("");
    let current = { ...d, files: d.files.map((f) => ({ ...f })) };
    try {
      for (let i = 0; i < current.files.length; i++) {
        const f = current.files[i];
        if (f.mediaId) continue;
        setProgress(`Загрузка файла ${i + 1} из ${current.files.length}…`);
        const data = new FormData();
        data.append("file", f.file);
        const media = await api<Media>("/media", {
          method: "POST",
          headers: { "X-Upload-ID": f.key },
          body: data,
        });
        f.mediaId = media.id;
        f.kind = media.kind;
        await saveDraft(user.id, current);
        setDraft({ ...current, files: [...current.files] });
      }
      setProgress("Отправляем обращение…");
      const payload = current.pendingPayload || {
        event_id: current.event_id,
        category: current.category,
        description: current.description,
        address: current.address,
        latitude: current.latitude,
        longitude: current.longitude,
        location_source:
          current.latitude == null ? "unknown" : current.location_source,
        device_accuracy: current.device_accuracy,
        media_ids: current.files.map((f) => f.mediaId),
      };
      current = { ...current, pendingPayload: payload };
      await saveDraft(user.id, current);
      setDraft(current);
      const result = await api<Report>("/reports", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await clearDraft(user.id);
      router.replace("/reports/" + result.id + "?created=1");
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status >= 400 &&
        e.status < 500 &&
        e.status !== 409
      ) {
        delete current.pendingPayload;
        await saveDraft(user.id, current).catch(() => {});
      }
      setError((e as Error).message);
      setDraft(current);
      setBusy(false);
      setProgress("");
    }
  }
  return (
    <div className="create-layout">
      <div className="page-heading">
        <div className="eyebrow">ВАШЕ ВНИМАНИЕ МЕНЯЕТ ГОРОД</div>
        <h1>Сообщить о проблеме</h1>
        <p>Расскажите, что случилось. Остальное поможем уточнить.</p>
      </div>
      <div className="wizard-layout">
        <aside className="wizard-aside">
          <ol className="wizard-steps">
            {[
              "Проблема и материалы",
              "Место на карте",
              "Проверка и отправка",
            ].map((s, i) => (
              <li
                key={s}
                className={
                  i === d.step ? "current" : i < d.step ? "complete" : ""
                }
              >
                <span>{i < d.step ? <Check size={16} /> : i + 1}</span>
                <div>
                  {s}
                  <small>
                    {
                      [
                        "Фото, видео и описание",
                        "Точка или ориентир",
                        "Всё готово?",
                      ][i]
                    }
                  </small>
                </div>
              </li>
            ))}
          </ol>
          <div className="aside-note">
            <Save size={20} />
            <p>{saved || "Черновик хранится только на этом устройстве."}</p>
          </div>
        </aside>
        <section className="form-card">
          {restored && (
            <div className="notice" role="status">
              Черновик восстановлен. Продолжите с того места, где остановились.
              <button
                type="button"
                className="text-button"
                onClick={() => setRestored(false)}
              >
                Понятно
              </button>
            </div>
          )}
          <fieldset
            disabled={busy || !!d.pendingPayload}
            className="wizard-fields"
          >
            <legend className="sr-only">Создание обращения</legend>
            {d.step === 0 ? (
              <>
                <h2>Что случилось?</h2>
                <p className="muted">
                  Снимайте из безопасного места. Не выходите на проезжую часть
                  ради кадра.
                </p>
                <label htmlFor="category">Тип проблемы</label>
                <select
                  id="category"
                  value={d.category}
                  onChange={(e) => update({ category: e.target.value })}
                >
                  {Object.entries(categories).map(([v, t]) => (
                    <option value={v} key={v}>
                      {t}
                    </option>
                  ))}
                </select>
                <label htmlFor="description">
                  Опишите проблему <span aria-hidden>*</span>
                </label>
                <textarea
                  id="description"
                  value={d.description}
                  onChange={(e) => update({ description: e.target.value })}
                  rows={4}
                  minLength={5}
                  maxLength={3000}
                  placeholder="Например: глубокая яма у остановки, машинам приходится объезжать"
                />
                <div className="input-meta">
                  <span>Добавьте детали, которые помогут инспектору.</span>
                  <span>{d.description.length}/3000</span>
                </div>
                <label>
                  Фото или короткое видео <span aria-hidden>*</span>
                </label>
                <div className="upload-zone">
                  <ImagePlus size={30} />
                  <strong>Покажите проблему</strong>
                  <p>До 4 файлов · до 25 MB каждый · видео до 30 секунд</p>
                  <div className="upload-actions">
                    <label className="button secondary small file-button">
                      <Camera size={17} />
                      Снять фото
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        capture="environment"
                        onChange={addFiles}
                        aria-label="Снять фото"
                      />
                    </label>
                    <label className="button secondary small file-button">
                      <Video size={17} />
                      Снять видео
                      <input
                        type="file"
                        accept="video/mp4,video/webm,video/quicktime"
                        capture="environment"
                        onChange={addFiles}
                        aria-label="Снять видео"
                      />
                    </label>
                    <label className="button small file-button">
                      Выбрать файлы
                      <input
                        type="file"
                        multiple
                        accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime"
                        onChange={addFiles}
                        aria-label="Выбрать файлы"
                      />
                    </label>
                  </div>
                </div>
                <div className="preview-grid">
                  {d.files.map((f) => (
                    <FilePreview
                      key={f.key}
                      item={f}
                      onRemove={() =>
                        update({
                          files: d.files.filter((x) => x.key !== f.key),
                        })
                      }
                    />
                  ))}
                </div>
              </>
            ) : d.step === 1 ? (
              <>
                <h2>Где нужна помощь?</h2>
                <LocationFields
                  point={d}
                  address={d.address}
                  onAddress={(address) => update({ address })}
                  onPoint={(p, source, accuracy) =>
                    update({
                      ...p,
                      location_source: source,
                      device_accuracy:
                        source === "gps" ? (accuracy ?? null) : null,
                    })
                  }
                />
              </>
            ) : (
              <>
                <div className="eyebrow">ПОСЛЕДНИЙ ШАГ</div>
                <h2>Проверьте обращение</h2>
                <div className="review-summary">
                  <span className="category-label">
                    {categories[d.category]}
                  </span>
                  <p>{d.description}</p>
                  <div className="review-location">
                    <MapPin size={20} />
                    <div>
                      <strong>{d.address}</strong>
                      <p className="muted">
                        {d.latitude != null && d.longitude != null
                          ? `${d.latitude.toFixed(5)}, ${d.longitude.toFixed(5)} · точка указана`
                          : "Точка не указана — инспектор уточнит место"}
                      </p>
                    </div>
                  </div>
                  <p className="muted">Вложений: {d.files.length}</p>
                </div>
                <p className="hint">
                  После отправки обращение попадёт инспектору. Статус и ответ
                  появятся в разделе «Мои обращения».
                </p>
              </>
            )}
          </fieldset>
          <ErrorBox message={error} />
          {d.pendingPayload && !busy && (
            <p className="notice">
              Проверяем результат отправки. Повторите отправку с теми же данными
              — второе обращение не создастся.
            </p>
          )}
          {busy && (
            <p className="upload-progress" role="status">
              <Spinner />
              {progress} Обработка видео может занять до 90 секунд.
            </p>
          )}
          <div className="wizard-actions">
            {d.step > 0 ? (
              <button
                className="button secondary"
                disabled={busy || !!d.pendingPayload}
                onClick={() => update({ step: d.step - 1 })}
              >
                <ArrowLeft size={18} />
                Назад
              </button>
            ) : (
              <span />
            )}
            {d.step < 2 ? (
              <button className="button" onClick={next}>
                Продолжить <ArrowRight size={18} />
              </button>
            ) : (
              <button
                className="button"
                disabled={busy}
                aria-busy={busy}
                onClick={() => void submit()}
              >
                {busy ? <Spinner /> : <Check size={18} />}Отправить обращение
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
export function NewReport() {
  return (
    <AuthGate>
      <Form />
    </AuthGate>
  );
}
