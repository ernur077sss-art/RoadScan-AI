"use client";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, ArrowLeft, Phone, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "./providers";
import { ErrorBox, Spinner } from "./ui";
export function Login() {
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
