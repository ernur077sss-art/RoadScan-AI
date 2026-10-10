import assert from "node:assert/strict";
import { test } from "node:test";
import { apiOrigin } from "./deployment-config.mjs";

test("local and Docker development keep their API origins", () => {
  assert.equal(apiOrigin({}), "http://127.0.0.1:8000");
  assert.equal(
    apiOrigin({ API_INTERNAL_URL: "http://api:8000/" }),
    "http://api:8000",
  );
});

test("Vercel cannot silently ship localhost or sample configuration", () => {
  for (const API_INTERNAL_URL of [
    undefined,
    " ",
    "http://api.roadscan.kz",
    "https://localhost:8000",
    "https://127.0.0.1",
    "https://10.0.0.1",
    "https://[::1]",
    "https://api.internal",
    "https://api.example.com",
    "https://api.example",
  ]) {
    assert.throws(() => apiOrigin({ VERCEL: "1", API_INTERNAL_URL }));
  }
});

test("ambiguous paths and credential-bearing destinations are rejected", () => {
  for (const API_INTERNAL_URL of [
    "not a url",
    "ftp://api.roadscan.kz",
    "https://user:secret@api.roadscan.kz",
    "https://api.roadscan.kz/api",
    "https://api.roadscan.kz/?token=secret",
    "https://api.roadscan.kz/#fragment",
  ]) {
    assert.throws(() => apiOrigin({ API_INTERNAL_URL }));
  }
});

test("deployed origins normalize correctly without altering the API path", () => {
  assert.equal(
    apiOrigin({ VERCEL: "1", API_INTERNAL_URL: " https://API.roadscan.kz/ " }),
    "https://api.roadscan.kz",
  );
});

test("preview, branch and production frontend addresses cannot proxy to themselves", () => {
  for (const key of [
    "VERCEL_URL",
    "VERCEL_BRANCH_URL",
    "VERCEL_PROJECT_PRODUCTION_URL",
  ]) {
    assert.throws(
      () =>
        apiOrigin({
          VERCEL: "1",
          API_INTERNAL_URL: "https://roadscan.vercel.app",
          [key]: "roadscan.vercel.app",
        }),
      /proxy loop/,
    );
  }
});
