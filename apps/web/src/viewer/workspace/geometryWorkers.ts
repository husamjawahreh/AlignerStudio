/**
 * Worker-safe geometry operation boundary.
 * Heavy mesh work should cross this API with transferable buffers — not block the UI thread.
 */

export type GeometryWorkerOperation =
  | "compute_normals"
  | "compute_bounds"
  | "simplify_preview"
  | "build_bvh";

export interface GeometryWorkerRequest {
  operation: GeometryWorkerOperation;
  /** Transferable positions (Float32). */
  positions: Float32Array;
  indices?: Uint32Array;
  requestId: string;
}

export interface GeometryWorkerResponse {
  requestId: string;
  ok: boolean;
  error?: string;
  /** Optional result buffers — never clinical labels. */
  positions?: Float32Array;
  indices?: Uint32Array;
  bounds?: { min: [number, number, number]; max: [number, number, number] };
}

/**
 * Architecture stub: validates request shape. Full worker pool is a later package.
 * Guarantees we never attach fabricated FDI / clinical fields to worker I/O.
 */
export function validateGeometryWorkerRequest(request: GeometryWorkerRequest): string | null {
  if (!request.requestId) return "requestId is required";
  if (!request.positions || request.positions.length < 9) return "positions buffer is too small";
  if (request.indices && request.indices.length % 3 !== 0) return "indices must be triangle triplets";
  return null;
}

export const GEOMETRY_WORKER_FORBIDDEN_FIELDS = [
  "fdiNumber",
  "fdi",
  "clinicalIdentity",
  "confidence",
] as const;
