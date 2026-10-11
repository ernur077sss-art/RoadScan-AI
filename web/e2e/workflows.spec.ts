import { test, expect, type Page, type BrowserContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
const root = path.resolve(__dirname, "../..");
function phone() {
  return (
    "+7702" + String(Math.floor(Math.random() * 10000000)).padStart(7, "0")
  );
}
async function login(
  page: Page,
  number = phone(),
  password = "Тестовый пароль для E2E!",
) {
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Нет аккаунта? Зарегистрироваться" })
    .click();
  if (password.length > 4) {
    await page
      .getByRole("button", { name: "Использовать длинный пароль", exact: true })
      .click();
  } else {
    await expect(page.getByLabel("Пароль", { exact: true })).toHaveAttribute(
      "inputmode",
      "numeric",
    );
    await expect(page.getByLabel("Пароль", { exact: true })).toHaveAttribute(
      "maxlength",
      "4",
    );
  }
  await page.getByLabel("Номер телефона").fill(number);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByLabel("Повторите пароль").fill(password);
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "Зарегистрироваться", exact: true })
    .click();
  await expect(page).toHaveURL(/\/reports$/);
  return number;
}
function grantInspector(number: string) {
  execFileSync(
    process.env.ROADSCAN_E2E_PYTHON!,
    [
      "-m",
      "api.manage",
      "grant-role",
      "--phone",
      number,
      "--role",
      "inspector",
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        ROADSCAN_ENV: "test",
        ROADSCAN_DATA_DIR: process.env.ROADSCAN_E2E_DATA,
        ROADSCAN_DATABASE_URL:
          "sqlite:///" + path.join(process.env.ROADSCAN_E2E_DATA!, "test.db"),
      },
      stdio: "pipe",
    },
  );
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
}
const headers = { Origin: "http://localhost:3100", "X-RoadScan-Request": "1" };

test("PIN из четырёх цифр с ведущими нулями и повторный вход", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const number = await login(page, phone(), "0042");
  expect(
    (await page.request.post("/api/auth/logout", { headers })).status(),
  ).toBe(200);
  await page.goto("/login?next=/reports/new");
  await page.getByLabel("Номер телефона").fill(number);
  await page
    .getByLabel("Пароль", { exact: true })
    .fill("Неверный тестовый пароль");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.locator(".auth-card").getByRole("alert")).toContainText(
    "Неверный номер телефона или пароль",
  );
  await page.getByLabel("Пароль", { exact: true }).fill("0042");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).toHaveURL(/\/reports\/new$/);
  await noOverflow(page);
});

test("житель → черновик → повтор отправки → уточнение → инспектор → KPI", async ({
  page,
  browser,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 375, height: 812 });
  await login(page);
  await page.goto("/reports/new");
  await page
    .getByLabel("Опишите проблему")
    .fill("Тестовое обращение: глубокая яма у остановки на улице Абая.");
  await page
    .getByLabel("Выбрать файлы", { exact: true })
    .setInputFiles(path.join(root, "web/public/icon-192.png"));
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await page
    .getByLabel("Улица и ориентир")
    .fill("Семей, улица Абая, у остановки");
  await page.getByText("Указать координаты вручную", { exact: true }).click();
  await page.getByLabel("Широта", { exact: true }).pressSequentially("50.411");
  await page.getByLabel("Долгота", { exact: true }).pressSequentially("80.249");
  await expect(page.getByLabel("Широта", { exact: true })).toHaveValue(
    "50.411",
  );
  await expect(
    page.getByText("Черновик сохранён на этом устройстве", { exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(650);
  await page.reload();
  await expect(
    page.getByText("Черновик восстановлен.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByLabel("Улица и ориентир")).toHaveValue(
    "Семей, улица Абая, у остановки",
  );
  await noOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath("mobile-draft.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  let lost = false;
  await page.route("**/api/reports", async (route) => {
    if (route.request().method() === "POST" && !lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Отправить обращение", exact: true })
    .click();
  await expect(
    page.getByText("Проверяем результат отправки.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Отправить обращение", exact: true })
    .click();
  await expect(page).toHaveURL(/\/reports\/[\w-]+\?created=1/);
  const id = new URL(page.url()).pathname.split("/").pop()!;
  const own = await page.request.get("/api/reports");
  expect((await own.json()).length).toBe(1);
  await expect(page.locator(".status")).toHaveText("На проверке");
  await expect(page.locator(".evidence-grid img")).toBeVisible();
  const mediaUrl = await page.locator(".evidence-grid img").getAttribute("src");
  const inspectorContext = await browser.newContext({
    baseURL: "http://localhost:3100",
    viewport: { width: 1280, height: 900 },
  });
  const inspector = await inspectorContext.newPage();
  const number = await login(inspector);
  grantInspector(number);
  await inspector.goto("/inspector/reports/" + id);
  await inspector.getByLabel("Результат проверки").selectOption("needs_info");
  await inspector
    .getByLabel("Ответ жителю / причина изменения")
    .fill("Уточните, с какой стороны остановки находится яма.");
  await inspector
    .getByRole("button", { name: "Сохранить решение", exact: true })
    .click();
  await expect(inspector.locator(".status")).toHaveText("Нужно уточнение");
  await page.reload();
  await page
    .getByLabel("Ваше уточнение")
    .fill("Со стороны парка, прямо перед остановкой.");
  await page
    .getByRole("button", { name: "Отправить уточнение", exact: true })
    .click();
  await expect(page.locator(".status")).toHaveText("На проверке");
  await inspector.reload();
  await inspector.getByLabel("Место дефекта проверено").check();
  await inspector
    .getByLabel("Ответ жителю / причина изменения")
    .fill("Материалы и место проверены. Дефект подтверждён.");
  await inspector
    .getByRole("button", { name: "Сохранить решение", exact: true })
    .click();
  await expect(inspector.locator(".status")).toHaveText("Подтверждено");
  await page.reload();
  await expect(page.locator(".response-card")).toContainText(
    "Материалы и место проверены",
  );
  await expect(page.locator(".timeline li")).toHaveCount(4);
  await inspector.goto("/inspector");
  await expect(inspector.locator(".metric-card.featured strong")).toHaveText(
    "100%",
  );
  await inspector
    .getByRole("button", { name: "Показать карту", exact: true })
    .click();
  await expect(inspector.locator(".report-map-dot")).toHaveCount(1);
  await noOverflow(inspector);
  await inspector.screenshot({
    path: testInfo.outputPath("inspector-desktop.png"),
    fullPage: true,
  });
  const strangerContext = await browser.newContext({
    baseURL: "http://localhost:3100",
  });
  const stranger = await strangerContext.newPage();
  await login(stranger);
  expect((await stranger.request.get("/api/reports/" + id)).status()).toBe(404);
  expect((await stranger.request.get(mediaUrl!)).status()).toBe(404);
  expect((await stranger.request.get("/api/inspector/reports")).status()).toBe(
    403,
  );
  await strangerContext.close();
  await inspectorContext.close();
  expect(errors).toEqual([]);
});

test("адаптивность, темы, навигация с клавиатуры и PWA", async ({
  page,
}, testInfo) => {
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /Наш город/ }),
    ).toBeVisible();
    await noOverflow(page);
    await page.screenshot({
      path: testInfo.outputPath("home-" + width + ".png"),
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Включить тёмную тему" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.screenshot({
    path: testInfo.outputPath("home-dark.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Перейти к содержимому" }),
  ).toBeFocused();
  const manifest = await (
    await page.request.get("/manifest.webmanifest")
  ).json();
  expect(manifest.display).toBe("standalone");
  for (const icon of manifest.icons)
    expect((await page.request.get(icon.src)).status()).toBe(200);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.context().setOffline(true);
  await page.goto("/unavailable-offline");
  await expect(
    page.getByRole("heading", { name: "Сейчас нет связи" }),
  ).toBeVisible();
  await page.context().setOffline(false);
});
