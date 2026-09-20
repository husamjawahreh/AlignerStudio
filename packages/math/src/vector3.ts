/** Minimal, framework-agnostic 3D vector helpers used by the viewer. */
export interface Vector3Tuple {
  x: number;
  y: number;
  z: number;
}

export function addVectors(a: Vector3Tuple, b: Vector3Tuple): Vector3Tuple {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

export function subtractVectors(a: Vector3Tuple, b: Vector3Tuple): Vector3Tuple {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

export function scaleVector(v: Vector3Tuple, scalar: number): Vector3Tuple {
  return { x: v.x * scalar, y: v.y * scalar, z: v.z * scalar };
}

export function vectorLength(v: Vector3Tuple): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

/** Linear interpolation between two vectors, used for stage-to-stage playback. */
export function lerpVectors(a: Vector3Tuple, b: Vector3Tuple, t: number): Vector3Tuple {
  const clamped = Math.min(1, Math.max(0, t));
  return {
    x: a.x + (b.x - a.x) * clamped,
    y: a.y + (b.y - a.y) * clamped,
    z: a.z + (b.z - a.z) * clamped,
  };
}
