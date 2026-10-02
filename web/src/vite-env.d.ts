/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Branch whose data/ the snapshot links point to (set by the Pages build). */
  readonly VITE_DATA_BRANCH?: string;
}
