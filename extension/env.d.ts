// Settings read from extension/.env (see .env.example).
interface ImportMetaEnv {
  /** Backend address. Default: http://localhost:8000 */
  readonly WXT_API_URL?: string;
  /** "true" = use shared/mock-analysis.json instead of calling the backend. */
  readonly WXT_USE_MOCK?: string;
}
