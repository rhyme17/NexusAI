export function getBackendBaseUrl(): string {
  return process.env.PLAYWRIGHT_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

