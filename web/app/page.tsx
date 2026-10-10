import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Camera,
  MapPin,
  MessageCircle,
  ShieldCheck,
  Route,
  ChevronRight,
} from "lucide-react";
import { InstallPrompt } from "@/components/install";
export default function Home() {
  return (
    <div className="home">
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="live-dot" />
            СЕМЕЙ · ГОРОД НАЧИНАЕТСЯ С НАС
          </div>
          <h1>
            Наш город.
            <br />
            <span>Наше внимание.</span>
          </h1>
          <p className="hero-description">
            Хорошая дорога начинается с того,
            <br className="desktop-only" /> кто заметил проблему. Расскажите о
            ней —<br className="desktop-only" /> инспектор получит ваше
            обращение.
          </p>
          <div className="hero-actions">
            <Link href="/reports/new" className="button large">
              Сообщить о проблеме <ArrowUpRight size={22} />
            </Link>
            <Link href="/reports" className="text-link">
              Мои обращения <ArrowRight size={18} />
            </Link>
          </div>
          <p className="hero-note">
            <ShieldCheck size={16} />
            Вход по телефону. Ваши данные видны только уполномоченным
            сотрудникам.
          </p>
        </div>
        <div className="city-card" aria-label="Иллюстрация городского квартала">
          <div className="city-top">
            <span>
              <MapPin size={15} /> Наш Семей
            </span>
            <span>Начнём с дорог</span>
          </div>
          <div className="city-grid">
            <div className="city-river" />
            <div className="city-street street-one" />
            <div className="city-street street-two" />
            <div className="city-street street-three" />
            <div className="city-park park-one">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="city-park park-two">
              <span />
              <span />
              <span />
            </div>
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className={"building building-" + i} />
            ))}
            <div className="city-location">
              <MapPin size={32} />
            </div>
            <div className="city-note">
              <span className="note-icon">
                <Route size={20} />
              </span>
              <div>
                <strong>Здесь нужна помощь</strong>
                <small>Покажите место на карте</small>
              </div>
            </div>
          </div>
          <div className="city-bottom">
            <span>Замечать. Сообщать. Следить.</span>
            <span className="muted">Иллюстрация</span>
          </div>
        </div>
      </section>
      <section className="how-section" id="how">
        <div className="section-intro">
          <div>
            <div className="eyebrow">ПОНЯТНО НА КАЖДОМ ШАГЕ</div>
            <h2>
              От вашего фото
              <br />
              до ответа инспектора
            </h2>
          </div>
          <p>
            Несколько простых действий,
            <br />
            чтобы проблема стала видимой.
          </p>
        </div>
        <div className="steps-grid">
          {[
            {
              n: "01",
              Icon: Camera,
              title: "Покажите проблему",
              text: "Сделайте фото или короткое видео. Добавьте пару слов о том, что случилось.",
            },
            {
              n: "02",
              Icon: MapPin,
              title: "Отметьте место",
              text: "Укажите точку на карте или ориентир. Так инспектору будет проще найти дефект.",
            },
            {
              n: "03",
              Icon: MessageCircle,
              title: "Получите ответ",
              text: "Следите за статусом в личном кабинете. Уточнения и решение появятся там же.",
            },
          ].map((s) => (
            <article className="step-card" key={s.n}>
              <div className="step-top">
                <s.Icon size={25} />
                <span>{s.n}</span>
              </div>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="bottom-callout">
        <div>
          <h2>Каждое обращение имеет значение.</h2>
          <p>
            Яма, разрушенное покрытие или повреждённый люк — начните с одного
            сообщения.
          </p>
        </div>
        <Link href="/reports/new" className="button secondary">
          Создать обращение <ChevronRight size={18} />
        </Link>
      </section>
      <InstallPrompt />
    </div>
  );
}
