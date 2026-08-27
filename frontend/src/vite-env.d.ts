/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_USE_MOCK: string
  readonly VITE_MOCK_AUTH?: string
  readonly VITE_MOCK_SESSIONS?: string
  readonly VITE_MOCK_TASKS?: string
  readonly VITE_MOCK_FORMS?: string
  readonly VITE_MOCK_KNOWLEDGE?: string
  readonly VITE_MOCK_ADMIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
