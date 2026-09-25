/** Build typed geometry buffers without intermediate arrays from nested map/flatMap. */

export function float32PositionsFromVertices(
  vertices: ReadonlyArray<readonly [number, number, number] | number[]>,
): Float32Array {
  const positions = new Float32Array(vertices.length * 3);
  for (let index = 0; index < vertices.length; index += 1) {
    const vertex = vertices[index];
    const offset = index * 3;
    positions[offset] = vertex[0];
    positions[offset + 1] = vertex[1];
    positions[offset + 2] = vertex[2];
  }
  return positions;
}

export function uint32IndicesFromFaces(
  faces: ReadonlyArray<readonly [number, number, number] | number[]>,
): number[] {
  const indices = new Array<number>(faces.length * 3);
  for (let index = 0; index < faces.length; index += 1) {
    const face = faces[index];
    const offset = index * 3;
    indices[offset] = face[0];
    indices[offset + 1] = face[1];
    indices[offset + 2] = face[2];
  }
  return indices;
}
