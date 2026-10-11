"use client";
import Link from "next/link";
import { AlertCircle, ArrowRight, FileText, LoaderCircle } from "lucide-react";
import { useAuth } from "./providers";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { statuses } from "@/lib/api";
export function ErrorBox({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return message ? (
    <div className="error-message" role="alert">
      <AlertCircle size={20} />
      <div>
        {message}
        {retry && (
          <button className="text-button" onClick={retry}>
            Повторить
          </button>
        )}
      </div>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div role="status" aria-label="Загрузка" className="skeleton-stack">
      <div className="skeleton" />
      <div className="skeleton tall" />
      <div className="skeleton" />
    </div>
  );
}
export function Spinner() {
  return <LoaderCircle size={18} className="spinner" aria-hidden />;
}
export function Status({ status }: { status: string }) {
  return (
    <span className={"status status-" + status}>
      <span />
      {statuses[status] || status}
    </span>
  );
}
export function Empty({
  title = "Обращений пока нет",
  text = "Заметили проблему на дороге? Отправьте первое обращение.",
  action = true,
}: {
  title?: string;
  text?: string;
  action?: boolean;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <FileText size={30} />
      </div>
      <h2>{title}</h2>
      <p>{text}</p>
      {action && (
        <Link href="/reports/new" className="button">
          Сообщить о проблеме <ArrowRight size={18} />
        </Link>
      )}
    </div>
  );
}
export function AuthGate({
  children,
  inspector = false,
}: {
  children: ReactNode;
  inspector?: boolean;
}) {
  const path = usePathname();
  const { user, loading, error, refresh } = useAuth();
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} retry={() => void refresh()} />;
  if (!user)
    return (
      <div className="empty-state">
        <div className="eyebrow">ВАШИ ОБРАЩЕНИЯ — В ОДНОМ МЕСТЕ</div>
        <h1>Сначала войдите</h1>
        <p>
          Войдите в аккаунт, чтобы отправлять обращения и видеть ответы
          инспектора.
        </p>
        <Link
          className="button"
          href={"/login?next=" + encodeURIComponent(path)}
        >
          Войти по телефону <ArrowRight size={18} />
        </Link>
      </div>
    );
  if (inspector && user.role === "citizen")
    return (
      <Empty
        title="Этот раздел для инспекторов"
        text="Доступ выдаёт администратор. Ваши обращения доступны в личном кабинете."
        action={false}
      />
    );
  return <>{children}</>;
}
