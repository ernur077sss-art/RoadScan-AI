"use client";
import { useEffect, useState } from "react";
import { Smartphone, Download } from "lucide-react";
type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
};
export function InstallPrompt() {
  const [event, setEvent] = useState<InstallEvent | null>(null),
    [installed, setInstalled] = useState(false);
  useEffect(() => {
    setInstalled(window.matchMedia("(display-mode: standalone)").matches);
    const listener = (e: Event) => {
      e.preventDefault();
      setEvent(e as InstallEvent);
    };
    const done = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", listener);
    window.addEventListener("appinstalled", done);
    return () => {
      window.removeEventListener("beforeinstallprompt", listener);
      window.removeEventListener("appinstalled", done);
    };
  }, []);
  if (installed) return null;
  return (
    <div className="install-card">
      <Smartphone size={25} />
      <div>
        <strong>Пусть город будет под рукой</strong>
        <p>
          {event
            ? "Добавьте приложение на главный экран телефона."
            : "На iPhone: «Поделиться» → «На экран Домой». На Android: меню браузера → «Установить приложение»."}
        </p>
      </div>
      {event && (
        <button
          className="button secondary"
          onClick={async () => {
            await event.prompt();
            const choice = await event.userChoice;
            if (choice.outcome === "accepted") setInstalled(true);
            setEvent(null);
          }}
        >
          <Download size={17} />
          Установить
        </button>
      )}
    </div>
  );
}
