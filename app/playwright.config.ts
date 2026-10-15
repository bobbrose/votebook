import { defineConfig, devices } from "@playwright/test";

const PORT = 5181;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, viewport: { width: 360, height: 740 } },
  projects: [
    { name: "mobile-chromium", use: { ...devices["Pixel 5"], viewport: { width: 360, height: 740 } } },
    { name: "mobile-webkit", use: { ...devices["iPhone 13"], viewport: { width: 360, height: 740 } } },
  ],
  webServer: {
    // The fictional fixture ballot, never real data, so tests are deterministic.
    command: `BALLOT_DATA_DIR=tests/fixtures/data npx vite --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,
  },
});
