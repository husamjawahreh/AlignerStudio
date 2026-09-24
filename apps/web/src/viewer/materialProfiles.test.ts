import { describe, expect, it } from "vitest";
import {
  dentalMaterialProfiles,
  enamelProfileForArch,
  profileColor,
} from "./materialProfiles";

describe("viewer presentation profiles", () => {
  it("keeps upper/lower enamel visually distinct without sharing the same color", () => {
    const upper = enamelProfileForArch("upper");
    const lower = enamelProfileForArch("lower");
    expect(profileColor(upper.color, 0)).not.toBe(profileColor(lower.color, 0));
    expect(profileColor(upper.color, 0)).toBe(profileColor(dentalMaterialProfiles.enamelUpper.color, 0));
    expect(profileColor(lower.color, 0)).toBe(profileColor(dentalMaterialProfiles.enamelLower.color, 0));
  });

  it("exposes only material presentation fields (no geometry or clinical payloads)", () => {
    const presentationKeys = new Set([
      "color",
      "roughness",
      "metalness",
      "envMapIntensity",
      "emissive",
      "emissiveIntensity",
      "transparent",
      "opacity",
      "depthWrite",
      "side",
    ]);
    const samples = [
      dentalMaterialProfiles.enamelUpper,
      dentalMaterialProfiles.enamelLower,
      dentalMaterialProfiles.enamelSelected,
      dentalMaterialProfiles.originalScanUpper,
      dentalMaterialProfiles.originalScanLower,
    ];
    for (const profile of samples) {
      for (const key of Object.keys(profile)) {
        expect(presentationKeys.has(key)).toBe(true);
      }
      expect("vertices" in profile).toBe(false);
      expect("faces" in profile).toBe(false);
      expect("movement" in profile).toBe(false);
      expect("centroid" in profile).toBe(false);
    }
  });

  it("does not mutate caller-owned tooth geometry when resolving arch tint", () => {
    const tooth = {
      arch: "upper" as const,
      vertices: [[1, 2, 3] as [number, number, number]],
      faces: [[0, 0, 0] as [number, number, number]],
      movement: { translationX: 0.5, translationY: 0, translationZ: 0 },
    };
    const before = structuredClone(tooth);
    void enamelProfileForArch(tooth.arch);
    expect(tooth).toEqual(before);
  });
});
