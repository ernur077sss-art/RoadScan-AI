"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="empty-state" role="alert">
      <h1>Не удалось открыть страницу</h1>
      <p>Попробуйте ещё раз. Уже отправленные обращения остаются в базе.</p>
      <button className="button" onClick={reset}>
        Повторить
      </button>
    </div>
  );
}
