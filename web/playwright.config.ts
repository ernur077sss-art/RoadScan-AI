import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
const root = path.resolve(__dirname, "..");
const data =
  process.env.ROADSCAN_E2E_DATA ||
  path.join(root, ".data", "e2e-" + Date.now());
fs.mkdirSync(data, { recursive: true });
const python =
  process.env.ROADSCAN_PYTHON || path.join(root, ".venv", "bin", "python");
process.env.ROADSCAN_E2E_DATA = data;
process.env.ROADSCAN_E2E_PYTHON = python;
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 15000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3100",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: fs.existsSync(chrome) ? { executablePath: chrome } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" -m uvicorn api.main:app --host 127.0.0.1 --port 8100 --no-access-log --no-proxy-headers`,
      cwd: root,
      url: "http://127.0.0.1:8100/api/health",
      reuseExistingServer: false,
      env: {
        ROADSCAN_ENV: "test",
        ROADSCAN_DATABASE_URL: "sqlite:///" + path.join(data, "test.db"),
        ROADSCAN_DATA_DIR: data,
        ROADSCAN_ORIGIN: "http://localhost:3100",
        ROADSCAN_SMS_MODE: "development",
        ROADSCAN_109_MODE: "disabled",
      },
    },
    {
      command: "pnpm exec next dev --hostname 127.0.0.1 --port 3100",
      url: "http://localhost:3100",
      reuseExistingServer: false,
      timeout: 120000,
      env: {
        NEXT_TELEMETRY_DISABLED: "1",
        API_INTERNAL_URL: "http://127.0.0.1:8100",
      },
    },
  ],
});
