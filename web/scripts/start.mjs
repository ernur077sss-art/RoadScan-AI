import { cpSync, existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = path.resolve(import.meta.dirname, "..");
const standalone = path.join(root, ".next/standalone");
if (!existsSync(path.join(standalone, "server.js")))
  throw new Error("Сначала выполните pnpm build");
cpSync(path.join(root, "public"), path.join(standalone, "public"), {
  recursive: true,
});
cpSync(path.join(root, ".next/static"), path.join(standalone, ".next/static"), {
  recursive: true,
});
process.env.HOSTNAME = process.env.ROADSCAN_BIND || "127.0.0.1";
process.env.PORT = process.env.PORT || "3000";
process.env.NEXT_TELEMETRY_DISABLED = "1";
await import(pathToFileURL(path.join(standalone, "server.js")).href);
