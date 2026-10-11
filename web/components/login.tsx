"use client";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, ArrowLeft, Phone, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "./providers";
import { ErrorBox, Spinner } from "./ui";
function SmsLogin() {
  const [phone, setPhone] = useState("+7"),
    [code, setCode] = useState(""),
    [consent, setConsent] = useState(false),
    [challenge, setChallenge] = useState<{
      challenge_id: string;
      development_code?: string;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const router = useRouter(),
    params = useSearchParams(),
    { refresh } = useAuth();
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!challenge) {
        setChallenge(
          await api("/auth/request", {
            method: "POST",
            body: JSON.stringify({ phone, consent }),
          }),
        );
      } else {
        await api("/auth/verify", {
          method: "POST",
          body: JSON.stringify({ challenge_id: challenge.challenge_id, code }),
        });
        await refresh();
        const next = params.get("next");
        router.replace(
          next && /^\/(reports|inspector)(\/|$)/.test(next) ? next : "/reports",
        );
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <div className="auth-message">
        <div className="eyebrow">ПРОСТО БЫТЬ НЕРАВНОДУШНЫМ</div>
        <h1>
          Ваша связь
          <br />с городом.
        </h1>
        <p>
          Отправляйте обращения и получайте ответы инспектора в одном месте.
        </p>
        <div className="auth-reassurance">
          <ShieldCheck size={24} />
          <p>
            Ваш телефон не публикуется на карте и недоступен другим жителям.
          </p>
        </div>
      </div>
      <section className="auth-card">
        <span className="form-icon">
          <Phone size={25} />
        </span>
        <h2>{challenge ? "Введите код" : "Войти по телефону"}</h2>
        <p className="muted">
          {challenge
            ? `Код для номера ${phone}`
            : "Подтвердите номер, чтобы создать личный кабинет."}
        </p>
        <form onSubmit={submit} aria-busy={busy}>
          {!challenge ? (
            <>
              <label htmlFor="phone">Номер телефона</label>
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                placeholder="+7 701 123 45 67"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                maxLength={22}
              />
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  required
                />
                <span>
                  Согласен на обработку данных для приёма и рассмотрения
                  обращений. <Link href="/privacy">Условия и данные</Link>
                </span>
              </label>
            </>
          ) : (
            <>
              <label htmlFor="code">Код из SMS</label>
              <input
                id="code"
                className="otp-input"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
              />
              {challenge.development_code && (
                <div className="test-code">
                  <strong>Тестовый режим — SMS не отправлялось</strong>
                  <p>
                    Код для локальной проверки:{" "}
                    <code>{challenge.development_code}</code>
                  </p>
                </div>
              )}
            </>
          )}
          <ErrorBox message={error} />
          <button
            className="button full"
            disabled={busy || (!challenge && !consent)}
          >
            {busy ? <Spinner /> : null}
            {challenge ? "Подтвердить и войти" : "Получить код"}
            <ArrowRight size={18} />
          </button>
          {challenge && (
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setChallenge(null);
                setCode("");
                setError("");
              }}
            >
              <ArrowLeft size={16} />
              Изменить номер / запросить новый код
            </button>
          )}
        </form>
        <p className="form-footnote">
          При первом входе аккаунт создаётся автоматически. Код действует 5
          минут.
        </p>
      </section>
    </div>
  );
}

export function Login() {
  const { health } = useAuth();
  if (!health)
    return (
      <section className="auth-card" aria-label="Подключение к сервису">
        <h1>Подключаемся к сервису</h1>
        <p className="muted" role="status">
          Первый запуск сервера после перерыва может занять около минуты.
        </p>
        <button
          className="button secondary"
          onClick={() => window.location.reload()}
        >
          Повторить подключение
        </button>
      </section>
    );
  return health.auth_mode === "password" ? <PasswordLogin /> : <SmsLogin />;
}

function PasswordLogin() {
  const [registering, setRegistering] = useState(false);
  const [longPassword, setLongPassword] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [phone, setPhone] = useState("+7");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { refresh } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const pinRegistration = registering && !longPassword;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setError("");
    if (registering && password !== confirmation) {
      setError("Пароли не совпадают");
      (
        e.currentTarget.elements.namedItem("confirmation") as HTMLInputElement
      )?.focus();
      return;
    }
    setBusy(true);
    try {
      await api(registering ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify({
          phone,
          password,
          ...(registering ? { consent } : {}),
        }),
      });
      setPassword("");
      setConfirmation("");
      await refresh();
      const next = params.get("next");
      router.replace(
        next && /^\/(reports|inspector)(\/|$)/.test(next) ? next : "/reports",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <div className="auth-message">
        <div className="eyebrow">ПРОСТО БЫТЬ НЕРАВНОДУШНЫМ</div>
        <h1>
          Ваша связь
          <br />с городом.
        </h1>
        <p>
          Отправляйте обращения и получайте ответы инспектора в одном месте.
        </p>
        <div className="auth-reassurance">
          <ShieldCheck size={24} />
          <p>
            Ваш телефон не публикуется на карте и недоступен другим жителям.
          </p>
        </div>
      </div>
      <section className="auth-card">
        <span className="form-icon">
          <Phone size={25} />
        </span>
        <h2>{registering ? "Создать аккаунт" : "Войти в свой аккаунт"}</h2>
        <p className="muted">
          {registering
            ? "Укажите свой номер и придумайте пароль. SMS не требуется."
            : "Номер телефона и пароль, указанные при регистрации."}
        </p>
        <form onSubmit={submit} aria-busy={busy}>
          <fieldset
            disabled={busy}
            style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
          >
            <label htmlFor="phone">Номер телефона</label>
            <input
              id="phone"
              name="phone"
              type="tel"
              autoComplete="username"
              placeholder="+7 701 123 45 67"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              maxLength={22}
            />
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              inputMode={pinRegistration ? "numeric" : undefined}
              autoComplete={registering ? "new-password" : "current-password"}
              spellCheck={false}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={registering ? (pinRegistration ? 4 : 15) : 1}
              maxLength={pinRegistration ? 4 : 128}
              pattern={pinRegistration ? "[0-9]{4}" : undefined}
              title={pinRegistration ? "Введите ровно 4 цифры" : undefined}
              aria-describedby={registering ? "password-hint" : undefined}
            />
            {registering && (
              <>
                <p id="password-hint" className="muted">
                  {pinRegistration
                    ? "Придумайте 4 цифры — это ваш постоянный PIN для входа."
                    : "От 15 символов. Можно использовать длинную фразу."}{" "}
                  Сохраните пароль: восстановление через SMS недоступно.
                </p>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => {
                    setLongPassword(!longPassword);
                    setPassword("");
                    setConfirmation("");
                    setError("");
                  }}
                >
                  {longPassword
                    ? "Использовать PIN из 4 цифр"
                    : "Использовать длинный пароль"}
                </button>
                <label htmlFor="confirmation">Повторите пароль</label>
                <input
                  id="confirmation"
                  name="confirmation"
                  type={showPassword ? "text" : "password"}
                  inputMode={pinRegistration ? "numeric" : undefined}
                  autoComplete="new-password"
                  spellCheck={false}
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  required
                  minLength={pinRegistration ? 4 : 15}
                  maxLength={pinRegistration ? 4 : 128}
                  pattern={pinRegistration ? "[0-9]{4}" : undefined}
                  title={pinRegistration ? "Введите ровно 4 цифры" : undefined}
                  aria-invalid={error === "Пароли не совпадают" || undefined}
                  aria-describedby={
                    error === "Пароли не совпадают"
                      ? "password-form-error"
                      : undefined
                  }
                />
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    required
                  />
                  <span>
                    Согласен на обработку данных для приёма и рассмотрения
                    обращений. <Link href="/privacy">Условия и данные</Link>
                  </span>
                </label>
              </>
            )}
            <button
              type="button"
              className="text-button"
              aria-pressed={showPassword}
              onClick={() => setShowPassword(!showPassword)}
            >
              {showPassword ? "Скрыть пароль" : "Показать пароль"}
            </button>
            <div id="password-form-error">
              <ErrorBox message={error} />
            </div>
            <button
              className="button full"
              disabled={busy || (registering && !consent)}
            >
              {busy && <Spinner />}
              {registering ? "Зарегистрироваться" : "Войти"}
              <ArrowRight size={18} />
            </button>
          </fieldset>
        </form>
        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={() => {
            setRegistering(!registering);
            setLongPassword(false);
            setShowPassword(false);
            setError("");
            setPassword("");
            setConfirmation("");
          }}
        >
          {registering
            ? "Уже есть аккаунт? Войти"
            : "Нет аккаунта? Зарегистрироваться"}
        </button>
        <p className="muted">
          Номер служит логином. Он не подтверждает личность владельца.
        </p>
      </section>
    </div>
  );
}
