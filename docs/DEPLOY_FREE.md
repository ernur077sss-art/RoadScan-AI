# Бесплатный конкурсный стенд

Продолжение этапов **2 — инфраструктура, 3 — вход и 8 — деплой/проверка** [плана](PLAN.md). Условие пользователя: **только бесплатные сервисы и программы**. Платные подписки, SMS, домены, дополнительные workers, диски и автоматические апгрейды не подключаем. При запросе банковской карты или оплаты — остановить этот шаг, не переключаться на платный тариф.

## Состав

| Сервис | Назначение | Тариф и ограничения |
|---|---|---|
| Vercel | Next.js/PWA, HTTPS, `/api/*` rewrite | Hobby; стандартный бесплатный `vercel.app` адрес, лимиты плана |
| Render | FastAPI + FFmpeg в Docker | Free: 512 MB, 0.1 CPU, засыпает после 15 минут без запросов; первый запуск может занять около минуты |
| Supabase | PostgreSQL/PostGIS и закрытые фото/видео через S3 API | Free: 500 MB БД, 1 GB файлов; лимиты трафика и паузы неактивных проектов |
| Вход | Телефон + пароль | Собственный API, без SMS и внешнего платного auth-сервиса |

Официальные условия: [Render Free](https://render.com/docs/free), [Render compute](https://render.com/docs/compute-plans), [Supabase Free](https://supabase.com/docs/guides/platform/billing-on-supabase), [Vercel Hobby](https://vercel.com/docs/plans/hobby). Бесплатные квоты не означают неограниченную работу. До запуска сверить текущие лимиты. Не подключать карту, автопополнение или платные дополнения. Не использовать искусственные запросы для обхода засыпания.

Это тестовый стенд с синтетическими данными. Бесплатные зарубежные регионы не являются согласованным контуром для приёма персональных данных жителей: условия настоящего городского пилота остаются в [OPERATIONS](OPERATIONS.md).

## 1. Supabase

1. Войти/создать аккаунт, создать организацию **Free** и проект `roadscan-ai`. Пароли и условия аккаунта подтверждает владелец. Регион — по возможности Frankfurt, рядом с API. Назначить надёжный пароль БД и сохранить его вне Git и чата.
2. **Выключить Data API** в настройках проекта до применения миграций. Веб не должен обращаться напрямую к таблицам через автоматически сгенерированный REST/GraphQL API. Доступ к таблицам выполняет только FastAPI со своими проверками ролей. [Рекомендация Supabase для DB-only использования](https://supabase.com/docs/guides/api/securing-your-api).
3. Подключение БД: использовать **Session pooler, порт 5432**, не Transaction pooler 6543. Приложению и миграциям нужны транзакции и session advisory lock. В Render записать URL с драйвером `postgresql+psycopg://`, URL-encoded паролем и `?sslmode=require`. [Подключение Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres).
   Альтернатива без ручного кодирования: убрать пароль из URL (`postgresql+psycopg://USER@HOST:5432/postgres?sslmode=require`) и задать **исходный пароль без изменений** отдельным секретом `ROADSCAN_DATABASE_PASSWORD`. Приложение само корректно закодирует спецсимволы. Непустая отдельная переменная заменяет пароль в URL.
4. Миграция создаёт PostGIS. Если расширение уже размещено в схеме `extensions`, убедиться, что эта схема входит в `search_path` серверной роли. Приложение использует geography и GiST.
5. В Storage создать **private** bucket `roadscan-evidence`; не включать public-доступ. Настроить S3 access keys только для серверного использования. Endpoint и region брать из панели проекта, endpoint имеет форму `https://PROJECT_REF.storage.supabase.co/storage/v1/s3`. [S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication).
6. S3-ключи обходят RLS и дают доступ к Storage: они допустимы только в секретах API, никогда в браузере или `NEXT_PUBLIC_*`. Клиент использует SigV4 и path-style, сохраняет `/storage/v1/s3` в пути.

Supabase S3 не поддерживает versioning. Для резервирования нужна отдельная копия объектов и БД; восстановление необходимо испытать. [S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility).

## 2. Render

Создать Web Service из `ernur077sss-art/RoadScan-AI`, ветка `main`, Dockerfile `Dockerfile.api`, **Free**, регион Frankfurt, health check `/api/health`. Либо импортировать [render.yaml](../render.yaml): он явно задаёт `plan: free`, один web service, без платных ресурсов.

При подключении GitHub выбирать доступ только к RoadScan-AI. Если репозиторий публичный, можно использовать его публичный Git URL вместо выдачи доступа к другим репозиториям.

Переменные из Blueprint:

| Переменная | Значение |
|---|---|
| `ROADSCAN_ENV` | `production` |
| `ROADSCAN_AUTH_MODE` | `password` |
| `ROADSCAN_ORIGIN` | Точный будущий постоянный HTTPS-адрес Vercel, без завершающего `/` |
| `ROADSCAN_DATABASE_URL` | Секретный URL Supabase Session pooler |
| `ROADSCAN_SECRET` | Случайный постоянный секрет 32+ символов; Blueprint генерирует при создании |
| `ROADSCAN_STORAGE` | `s3` |
| `ROADSCAN_S3_ENDPOINT`, `ROADSCAN_S3_BUCKET` | Endpoint и `roadscan-evidence` |
| `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 region и секреты Supabase |
| `ROADSCAN_MIGRATE_ON_START` | `1` |
| `ROADSCAN_109_MODE` | `disabled` |

Не менять `ROADSCAN_SECRET` между релизами: он шифрует телефоны. `.data` в контейнере нужна только для временной обработки; БД и вложения находятся в Supabase.

Free не поддерживает pre-deploy command, persistent disk и shell. Поэтому стартовый скрипт вызывает `python -m api.migrate` под блокировкой PostgreSQL перед Uvicorn; ошибка миграции останавливает запуск. Автодеплой Render в Blueprint выключен: новые версии публикуются вручную после проверки. Не создавать Render PostgreSQL Free — у него ограниченный срок жизни. [Blueprint reference](https://render.com/docs/blueprint-spec), [Free limitations](https://render.com/docs/free).

Назначение инспектора: сначала зарегистрировать тестовый аккаунт, затем выполнить `python -m api.manage grant-role --phone ... --role inspector` локально в окружении облачной БД и того же `ROADSCAN_SECRET`. Доступ к Render Shell для этого не нужен. Секреты передавать через локальное окружение без записи в историю или Git. Не назначать роли автоматически по заявленному телефону.

## 3. Vercel

Проект `roadscan-ai`, Hobby, репозиторий RoadScan-AI, root directory **web**, Node **24.x**. В Environment Variables **Production** задать `API_INTERNAL_URL` — фактический HTTPS origin работающего API `onrender.com`. Команды сборки находятся в `web/vercel.json`. Базу и S3-ключи сюда не переносить.

После сборки подтвердить постоянный домен и тот же `ROADSCAN_ORIGIN` в Render. Если домен изменился, сначала обновить origin API. Публикацию выполнять после готовности API; не подставлять демонстрационный API для обхода проверки сборки.

**`localhost:3000` доступен на ноутбуке, где запущен сервер.** На телефоне `localhost` указывает на сам телефон. Для доступа из интернета нужен опубликованный HTTPS-адрес Vercel; одной локальной сборки недостаточно.

## 4. Проверка и ограничения

- `/api/health` через Vercel: `production`, `password`, `sms=disabled`, `postgresql`, `integration_109=disabled`.
- Регистрация → выход → вход по паролю; безопасная cookie; OTP-эндпоинты закрыты; чужие материалы и инспекторский API недоступны жителю.
- Фото → обращение → инспектор → уточнение → подтверждение → KPI. Перезапуск API сохраняет БД и вложения.
- Проверить приватность bucket и недоступность таблиц через Supabase Data API без серверных credentials.
- Испытать видео и загрузку больше 4.5 MB через внешний rewrite. У Vercel proxy таймаут 120 секунд; FFmpeg на 0.1 CPU и пробуждение Render могут не уложиться. Номинальный лимит 25 MB / 30 секунд не является подтверждением скорости обработки в облаке.
- Контролировать объём 1 GB Storage и квоты трафика; не удалять обращения автоматически ради лимита. При заполнении остановить приём новых файлов и решить архивирование с владельцем.
- Перед реальными данными: backup/restore PostgreSQL+S3, нагрузка, физические телефоны, оператор и политика хранения. Вход не подтверждает SIM-карту, восстановление пароля пока отсутствует. 109 и ИИ не подключены.

## Фактический статус

На 11 октября 2026 года код и миграции опубликованы; PostgreSQL/PostGIS и веб прошли GitHub Actions на коммите `caff363`.

- **Vercel:** проект `roadscan-ai` в команде `ernur1`, Hobby. Через API подтверждён закреплённый домен `roadscan-ai-mu.vercel.app`. Публичного deployment приложения ещё нет.
- **Supabase:** проект `roadscan-ai` (`obfqgvxbtlphvqajddwe`) создан в организации **RoadScan AI**, база **Healthy**. Подтверждены тариф **Free** и включённый spend cap. Фактический регион выбранного владельцем проекта — **West EU (Ireland), `eu-west-1`**. Data API выключен; private bucket `roadscan-evidence` создан. S3 endpoint: `https://obfqgvxbtlphvqajddwe.storage.supabase.co/storage/v1/s3`. После отдельного разрешения владельца создан серверный S3-ключ `roadscan-api`; значения добавлены в форму Render. Миграции приложения ещё не применены.
- **Render:** вход через GitHub завершён, аккаунт активирован. Подготовлена форма `roadscan-api`: публичный Git URL только RoadScan-AI, `main`, Docker, `Dockerfile.api`, Frankfurt, **Free $0**, health check `/api/health`, auto-deploy Off. Переменные и секрет приложения заполнены, кроме известного только владельцу пароля БД. Форма ещё не отправлена, сервис API не создан.

Следующие действия: владелец вводит исходный пароль БД в `ROADSCAN_DATABASE_PASSWORD` в подготовленной форме Render; затем развернуть API, Vercel и проверить полный сценарий через HTTPS. Для БД выбран бесплатный Session pooler `aws-0-eu-west-1.pooler.supabase.com:5432`, пользователь `postgres.obfqgvxbtlphvqajddwe`, база `postgres`, `sslmode=require`. Карта, платные тарифы и дополнения не подключались. Секреты не передавать в чат или Git.

## Временная ссылка для проверки на телефоне

11 октября запущен отдельный тестовый экземпляр через бесплатный [Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Текущий адрес сохранён локально в `.data/phone-preview/public-url.txt`; при пересоздании туннеля он меняется. Это продолжение этапов **4, 6 и 8**, а не завершение постоянного размещения на Vercel/Render.

- Next.js собран отдельно в `.data/phone-preview/web`, слушает только `127.0.0.1:3001` и направляет API на `127.0.0.1:8001`.
- API использует отдельную SQLite-базу и локальные вложения в `.data/phone-preview/data`. Прежние обращения и облачные секреты в тестовый экземпляр не переносились. Вход — пароль, OTP и 109 отключены, разрешён точный HTTPS origin выданной ссылки; cookie имеет Secure/HttpOnly/SameSite.
- Снаружи проверены регистрация, выход/вход, загрузка изображения, создание обращения с координатами и приватность вложения. Мобильные страницы просмотрены при ширине 390 px. Камера, GPS, видео и установка PWA на физических устройствах ещё требуют проверки.
- Ссылка работает, пока запущены API, веб и `cloudflared`, ноутбук не спит и имеет интернет. Это временный тестовый доступ без гарантии доступности. Данные остаются на ноутбуке и не синхронизируются с будущей облачной базой.

Использован официальный `cloudflared` 2026.10.0 для macOS arm64; архив проверен по SHA-256 метаданных GitHub release. Программа находится в игнорируемой `.data/tools/`, без системной установки и платного аккаунта. Для остановки доступа достаточно завершить процесс туннеля; база и файлы сохранятся.
