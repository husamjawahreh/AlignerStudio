/// <reference types="vite/client" />
/// <reference types="three-mesh-bvh" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
