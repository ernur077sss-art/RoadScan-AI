"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home,
  FileText,
  Plus,
  MapPin,
  ArrowUpRight,
  Moon,
  Sun,
  LogOut,
  ShieldCheck,
  Menu,
  X,
  WifiOff,
} from "lucide-react";
import { useState, useEffect, type ReactNode } from "react";
import { useAuth } from "./providers";
export function Shell({ children }: { children: ReactNode }) {
  const { user, health, logout } = useAuth(),
    path = usePathname(),
    router = useRouter();
  const [menu, setMenu] = useState(false),
    [dark, setDark] = useState(false),
    [offline, setOffline] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  useEffect(() => {
    setMenu(false);
  }, [path]);
  useEffect(() => {
    if (!menu) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [menu]);
  const nav = [
    { href: "/", label: "Обзор", icon: Home },
    { href: "/reports", label: "Мои обращения", icon: FileText },
    ...(user?.role !== "citizen" && user
      ? [{ href: "/inspector", label: "Инспектор", icon: ShieldCheck }]
      : []),
  ];
  function theme() {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("roadscan-theme", next ? "dark" : "light");
    } catch {
      /* Theme still works when storage is blocked. */
    }
    setDark(next);
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Перейти к содержимому
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Link
            href="/"
            className="brand"
            aria-label="Народный контроль — главная"
          >
            <span className="brand-mark">
              <MapPin size={25} aria-hidden />
            </span>
            <span>
              Народный контроль<small>ДОРОГИ СЕМЕЯ</small>
            </span>
          </Link>
          <nav className="desktop-nav" aria-label="Основная навигация">
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={path === n.href ? "active" : ""}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="header-actions">
            <button
              className="icon-button"
              onClick={theme}
              aria-label={
                dark ? "Включить светлую тему" : "Включить тёмную тему"
              }
            >
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            {user ? (
              <button
                className="icon-button"
                aria-label="Выйти"
                onClick={() =>
                  void logout()
                    .then(() => router.push("/"))
                    .catch((e) => setError(e.message))
                }
              >
                <LogOut size={19} />
              </button>
            ) : (
              <Link href="/login" className="button small secondary">
                Войти <ArrowUpRight size={16} />
              </Link>
            )}
            <button
              className="icon-button mobile-menu"
              aria-label="Меню"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
        </div>
        {menu && (
          <nav className="mobile-dropdown" aria-label="Мобильная навигация">
            {nav.map((n) => (
              <Link key={n.href} href={n.href}>
                <n.icon size={18} />
                {n.label}
              </Link>
            ))}
          </nav>
        )}
      </header>
      {health && health.environment !== "production" && (
        <div className="dev-banner">
          <span className="dev-dot" />
          Локальный пилот ·{" "}
          {health.auth_mode === "password"
            ? "Вход по телефону и паролю"
            : health.sms === "development"
              ? "SMS заменены тестовым кодом"
              : "SMS-провайдер настроен"}{" "}
          · 109{" "}
          {health.integration_109 === "simulator"
            ? "в режиме симулятора"
            : "не подключён"}
        </div>
      )}
      {offline && (
        <div className="offline-banner" role="status">
          <WifiOff size={17} />
          Нет интернета. Сохраните черновик; отправить его можно после
          восстановления связи.
        </div>
      )}
      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}
      <main id="main" className="main-content">
        {children}
      </main>
      <footer className="site-footer">
        <span>
          Народный контроль <span className="muted">/ RoadScan</span>
        </span>
        <Link href="/privacy">Данные и конфиденциальность</Link>
        <span className="muted">Сделаем город внимательнее</span>
      </footer>
      <nav className="bottom-nav" aria-label="Быстрый доступ">
        <Link href="/" aria-current={path === "/" ? "page" : undefined}>
          <Home size={20} />
          Главная
        </Link>
        <Link href="/reports/new" className="bottom-create">
          <Plus size={22} />
          Сообщить
        </Link>
        <Link
          href="/reports"
          aria-current={path === "/reports" ? "page" : undefined}
        >
          <FileText size={20} />
          Обращения
        </Link>
      </nav>
    </>
  );
}
