import Link from "next/link";
export default function NotFound() {
  return (
    <div className="empty-state">
      <div className="eyebrow">404</div>
      <h1>Страница не найдена</h1>
      <p>Возможно, адрес изменился. Вернитесь к своим обращениям.</p>
      <Link href="/reports" className="button">
        Мои обращения
      </Link>
    </div>
  );
}
