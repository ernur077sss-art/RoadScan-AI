/** Resolve the build-time API origin without exposing backend credentials. */
export function apiOrigin(env = process.env) {
  const onVercel = env.VERCEL === "1";
  const value = env.API_INTERNAL_URL?.trim();
  if (!value && onVercel) {
    throw new Error(
      "Set API_INTERNAL_URL to the public HTTPS origin of the RoadScan API in Vercel, then redeploy. See docs/DEPLOY_VERCEL.md.",
    );
  }
  let url;
  try {
    url = new URL(value || "http://127.0.0.1:8000");
  } catch {
    throw new Error("API_INTERNAL_URL must be a valid HTTP(S) origin.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  ) {
    throw new Error(
      "API_INTERNAL_URL must contain only scheme and host (optional port), without /api, credentials, query or fragment.",
    );
  }
  if (onVercel) {
    const host = url.hostname.toLowerCase();
    if (
      url.protocol !== "https:" ||
      !host.includes(".") ||
      /^[\d.]+$/.test(host) ||
      host.includes(":") ||
      /(?:^|\.)(localhost|local|internal|test|invalid|example)$/.test(host) ||
      /(?:^|\.)example\.(com|org|net)$/.test(host)
    ) {
      throw new Error(
        "On Vercel, API_INTERNAL_URL must be a real public HTTPS hostname; local and example addresses are not deployable.",
      );
    }
    for (const key of [
      "VERCEL_URL",
      "VERCEL_BRANCH_URL",
      "VERCEL_PROJECT_PRODUCTION_URL",
    ]) {
      if (env[key] && host === new URL(`https://${env[key]}`).hostname) {
        throw new Error(
          "API_INTERNAL_URL points to this frontend. Use the separately hosted Python API to avoid a proxy loop.",
        );
      }
    }
  }
  return url.origin;
}
