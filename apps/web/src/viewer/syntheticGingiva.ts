/**
 * Gingiva presentation geometry.
 *
 * Real meshes are preferred when usable. Otherwise a synthetic envelope is
 * generated for viewport display only.
 *
 * PRESENTATION ONLY — must never feed treatment math, measurements, contacts,
 * collisions, proximity, staging, clinical validation, or clinical approval.
 */

export type GingivaArch = "upper" | "lower";

export interface GingivaSourceTooth {
  instanceId: number;
  arch: GingivaArch;
  vertices: readonly [number, number, number][];
  faces?: readonly [number, number, number][];
  centroid?: readonly [number, number, number];
}

export interface RealGingivaMeshInput {
  arch: GingivaArch;
  vertices: readonly [number, number, number][];
  faces: readonly [number, number, number][];
}

export interface GingivaPresentationMesh {
  arch: GingivaArch;
  vertices: [number, number, number][];
  faces: [number, number, number][];
  source: "real" | "synthetic";
  /** Marker for audit trails — always true for this module's output. */
  presentationOnly: true;
}

export interface ResolveGingivaOptions {
  includeUpper?: boolean;
  includeLower?: boolean;
  hiddenToothIds?: ReadonlySet<number>;
  /** Ring resolution around each tooth margin. */
  radialSegments?: number;
}

const MIN_REAL_VERTICES = 24;
const MIN_REAL_FACES = 12;

export function isUsableRealGingiva(
  meshes: readonly RealGingivaMeshInput[] | null | undefined,
): meshes is readonly RealGingivaMeshInput[] {
  if (!meshes || meshes.length === 0) return false;
  return meshes.some(
    (mesh) => mesh.vertices.length >= MIN_REAL_VERTICES && mesh.faces.length >= MIN_REAL_FACES,
  );
}

/**
 * Resolve gingiva meshes for the viewport.
 * Prefers usable real geometry; otherwise builds a synthetic envelope.
 */
export function resolveGingivaPresentation(
  teeth: readonly GingivaSourceTooth[],
  realGingiva?: readonly RealGingivaMeshInput[] | null,
  options: ResolveGingivaOptions = {},
): GingivaPresentationMesh[] {
  const includeUpper = options.includeUpper ?? true;
  const includeLower = options.includeLower ?? true;
  const hidden = options.hiddenToothIds ?? new Set<number>();

  if (isUsableRealGingiva(realGingiva)) {
    return realGingiva
      .filter((mesh) => (mesh.arch === "upper" ? includeUpper : includeLower))
      .filter((mesh) => mesh.vertices.length >= MIN_REAL_VERTICES && mesh.faces.length >= MIN_REAL_FACES)
      .map((mesh) => ({
        arch: mesh.arch,
        vertices: mesh.vertices.map((vertex) => [...vertex] as [number, number, number]),
        faces: mesh.faces.map((face) => [...face] as [number, number, number]),
        source: "real" as const,
        presentationOnly: true as const,
      }));
  }

  const visible = teeth.filter(
    (tooth) =>
      !hidden.has(tooth.instanceId) &&
      tooth.vertices.length >= 3 &&
      (tooth.arch === "upper" ? includeUpper : includeLower),
  );

  const meshes: GingivaPresentationMesh[] = [];
  for (const arch of ["upper", "lower"] as const) {
    const archTeeth = visible.filter((tooth) => tooth.arch === arch);
    if (archTeeth.length === 0) continue;
    const synthetic = buildSyntheticEnvelope(archTeeth, arch, visible, options.radialSegments ?? 14);
    if (synthetic) meshes.push(synthetic);
  }
  return meshes;
}

function buildSyntheticEnvelope(
  archTeeth: readonly GingivaSourceTooth[],
  arch: GingivaArch,
  allVisibleTeeth: readonly GingivaSourceTooth[],
  radialSegments: number,
): GingivaPresentationMesh | null {
  const apical = apicalDirection(arch, allVisibleTeeth);
  const archCenter = meanPoints(archTeeth.map((tooth) => toothCentroid(tooth)));
  const sorted = [...archTeeth].sort(
    (left, right) =>
      toothAngle(toothCentroid(left), archCenter, apical) -
      toothAngle(toothCentroid(right), archCenter, apical),
  );

  const profiles = sorted.map((tooth) => cervicalProfile(tooth, apical, radialSegments));
  if (profiles.some((profile) => profile === null)) return null;
  const ready = profiles as CervicalProfile[];

  const bandCount = 4;
  const vertices: [number, number, number][] = [];
  const faces: [number, number, number][] = [];

  // Per tooth: bandCount rings from margin (tight) → apical bulk (soft, rounded).
  const ringIndex: number[][] = ready.map(() => []);
  ready.forEach((profile, toothIndex) => {
    for (let band = 0; band < bandCount; band += 1) {
      const t = band / (bandCount - 1);
      // Natural flare then soft tuck — avoids flat rectangular base.
      const radialScale = 1.04 + Math.sin(t * Math.PI) * 0.38 + t * 0.08;
      const apicalOffset = profile.marginRadius * (0.08 + t * 0.95);
      const papillaLift = Math.sin(t * Math.PI) * profile.marginRadius * 0.06;
      ringIndex[toothIndex].push(vertices.length);
      for (let i = 0; i < radialSegments; i += 1) {
        const angle = (i / radialSegments) * Math.PI * 2;
        // Slight scallop for gingival festooning (deterministic).
        const festoon = 1 + 0.045 * Math.sin(angle * 2 + toothIndex);
        const radial = profile.marginRadius * radialScale * festoon;
        const outward = add(
          scale(profile.axisU, Math.cos(angle) * radial),
          scale(profile.axisV, Math.sin(angle) * radial),
        );
        const point = add(
          add(profile.marginCenter, scale(apical, apicalOffset + papillaLift)),
          outward,
        );
        vertices.push(point);
      }
    }
  });

  const stitchRing = (aStart: number, bStart: number) => {
    for (let i = 0; i < radialSegments; i += 1) {
      const iNext = (i + 1) % radialSegments;
      const a0 = aStart + i;
      const a1 = aStart + iNext;
      const b0 = bStart + i;
      const b1 = bStart + iNext;
      faces.push([a0, b0, a1], [a1, b0, b1]);
    }
  };

  // Loft bands within each tooth and between neighboring teeth for continuity.
  for (let toothIndex = 0; toothIndex < ready.length; toothIndex += 1) {
    const rings = ringIndex[toothIndex];
    for (let band = 0; band < bandCount - 1; band += 1) {
      stitchRing(rings[band], rings[band + 1]);
    }
    if (toothIndex < ready.length - 1) {
      const next = ringIndex[toothIndex + 1];
      // Bridge mid + apical bands for continuous interdental gingiva/papilla.
      stitchRing(rings[1], next[1]);
      stitchRing(rings[2], next[2]);
      stitchRing(rings[bandCount - 1], next[bandCount - 1]);
    }
  }

  // Soft rounded end caps (not planar rectangles).
  addRoundedEndCap(vertices, faces, ringIndex[0], ready[0], apical, radialSegments, -1);
  addRoundedEndCap(
    vertices,
    faces,
    ringIndex[ready.length - 1],
    ready[ready.length - 1],
    apical,
    radialSegments,
    1,
  );

  if (vertices.length < 9 || faces.length < 8) return null;
  return {
    arch,
    vertices,
    faces,
    source: "synthetic",
    presentationOnly: true,
  };
}

interface CervicalProfile {
  marginCenter: [number, number, number];
  marginRadius: number;
  axisU: [number, number, number];
  axisV: [number, number, number];
}

function cervicalProfile(
  tooth: GingivaSourceTooth,
  apical: [number, number, number],
  _radialSegments: number,
): CervicalProfile | null {
  const center = toothCentroid(tooth);
  const scored = tooth.vertices.map((vertex) => ({
    vertex,
    score: dot(sub(vertex, center), apical),
  }));
  scored.sort((left, right) => right.score - left.score);
  const take = Math.max(3, Math.ceil(scored.length * 0.28));
  const apicalVertices = scored.slice(0, take).map((entry) => entry.vertex);
  const marginCenter = meanPoints(apicalVertices);
  const tangentBasis = orthonormalBasis(apical);
  const radii = apicalVertices.map((vertex) => {
    const offset = sub(vertex, marginCenter);
    const u = dot(offset, tangentBasis.u);
    const v = dot(offset, tangentBasis.v);
    return Math.hypot(u, v);
  });
  radii.sort((left, right) => left - right);
  const marginRadius = Math.max(radii[Math.floor(radii.length * 0.82)] ?? 0.35, 0.22);
  return {
    marginCenter,
    marginRadius,
    axisU: tangentBasis.u,
    axisV: tangentBasis.v,
  };
}

function addRoundedEndCap(
  vertices: [number, number, number][],
  faces: [number, number, number][],
  rings: number[],
  profile: CervicalProfile,
  apical: [number, number, number],
  radialSegments: number,
  side: 1 | -1,
): void {
  const outerStart = rings[rings.length - 1];
  const tip = add(
    add(profile.marginCenter, scale(apical, profile.marginRadius * 1.15)),
    scale(
      // Push tip slightly along arch tangent for a teardrop close, not a flat slab.
      side > 0 ? profile.axisU : scale(profile.axisU, -1),
      profile.marginRadius * 0.55,
    ),
  );
  const tipIndex = vertices.length;
  vertices.push(tip);
  for (let i = 0; i < radialSegments; i += 1) {
    const iNext = (i + 1) % radialSegments;
    faces.push([outerStart + i, tipIndex, outerStart + iNext]);
  }
}

function apicalDirection(
  arch: GingivaArch,
  teeth: readonly GingivaSourceTooth[],
): [number, number, number] {
  const upper = teeth.filter((tooth) => tooth.arch === "upper");
  const lower = teeth.filter((tooth) => tooth.arch === "lower");
  if (upper.length > 0 && lower.length > 0) {
    const separation = normalize(
      sub(meanPoints(upper.map(toothCentroid)), meanPoints(lower.map(toothCentroid))),
    );
    return arch === "upper" ? separation : scale(separation, -1);
  }
  return arch === "upper" ? [0, 1, 0] : [0, -1, 0];
}

function toothCentroid(tooth: GingivaSourceTooth): [number, number, number] {
  if (tooth.centroid) return [...tooth.centroid];
  return meanPoints(tooth.vertices);
}

function toothAngle(
  point: [number, number, number],
  center: [number, number, number],
  apical: [number, number, number],
): number {
  const offset = sub(point, center);
  const basis = orthonormalBasis(apical);
  return Math.atan2(dot(offset, basis.v), dot(offset, basis.u));
}

function orthonormalBasis(normal: [number, number, number]): {
  u: [number, number, number];
  v: [number, number, number];
} {
  const n = normalize(normal);
  const helper: [number, number, number] =
    Math.abs(n[1]) < 0.85 ? [0, 1, 0] : [1, 0, 0];
  const u = normalize(cross(helper, n));
  const v = normalize(cross(n, u));
  return { u, v };
}

function meanPoints(points: readonly [number, number, number][]): [number, number, number] {
  if (points.length === 0) return [0, 0, 0];
  const sum = points.reduce(
    (total, point) => [total[0] + point[0], total[1] + point[1], total[2] + point[2]] as [
      number,
      number,
      number,
    ],
    [0, 0, 0] as [number, number, number],
  );
  return [sum[0] / points.length, sum[1] / points.length, sum[2] / points.length];
}

function add(a: [number, number, number], b: [number, number, number]): [number, number, number] {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

function sub(a: [number, number, number], b: [number, number, number]): [number, number, number] {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function scale(v: [number, number, number], s: number): [number, number, number] {
  return [v[0] * s, v[1] * s, v[2] * s];
}

function dot(a: [number, number, number], b: [number, number, number]): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function cross(a: [number, number, number], b: [number, number, number]): [number, number, number] {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function normalize(v: [number, number, number]): [number, number, number] {
  const length = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / length, v[1] / length, v[2] / length];
}
