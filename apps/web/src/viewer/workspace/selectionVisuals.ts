/**
 * Selection visual language — presentation only.
 * Never invents clinical status; maps existing domain signals to visual roles.
 */

import type { IntelligenceTruthState } from "@alignerstudio/contracts";
import { dentalMaterialProfiles, enamelProfileForArch, profileColor } from "../materialProfiles";
import type { PresentationArch } from "../materialProfiles";

export type ToothVisualRole =
  | "normal"
  | "hovered"
  | "selected"
  | "multi_selected"
  | "hidden"
  | "requires_review"
  | "validation_warning"
  | "validation_error"
  | "treatment_target"
  | "unavailable";

export interface ToothVisualInput {
  arch: PresentationArch;
  selected: boolean;
  hovered: boolean;
  multiSelected?: boolean;
  hidden?: boolean;
  validationStatus?: "pass" | "warning" | "fail" | string | null;
  /** WP-02 overall tooth truth — optional. */
  truthState?: IntelligenceTruthState | null;
  isTreatmentTarget?: boolean;
}

export interface ToothVisualStyle {
  role: ToothVisualRole;
  color: number;
  emissive: number;
  emissiveIntensity: number;
  roughness: number;
  envMapIntensity: number;
  opacity: number;
  transparent: boolean;
}

/**
 * Resolve visual role without claiming clinical verification.
 * Selected/hovered dominate; validation severity next; truth-state only softens when not selected.
 */
export function resolveToothVisualRole(input: ToothVisualInput): ToothVisualRole {
  if (input.hidden) return "hidden";
  if (input.selected) return "selected";
  if (input.multiSelected) return "multi_selected";
  if (input.hovered) return "hovered";
  if (input.validationStatus === "fail") return "validation_error";
  if (input.validationStatus === "warning") return "validation_warning";
  if (input.isTreatmentTarget) return "treatment_target";
  if (input.truthState === "not_available") return "unavailable";
  if (input.truthState === "requires_review") return "requires_review";
  return "normal";
}

export function toothVisualStyle(input: ToothVisualInput): ToothVisualStyle {
  const role = resolveToothVisualRole(input);
  const base = enamelProfileForArch(input.arch);
  const baseColor = profileColor(base.color, input.arch === "upper" ? 0xf2e8d4 : 0xddd4c2);

  switch (role) {
    case "selected": {
      const profile = dentalMaterialProfiles.enamelSelected;
      return {
        role,
        color: profileColor(profile.color, 0xf4e6c8),
        emissive: profileColor(profile.emissive, 0x3d2a12),
        emissiveIntensity: Number(profile.emissiveIntensity ?? 0.12),
        roughness: Number(profile.roughness ?? 0.36),
        envMapIntensity: Number(profile.envMapIntensity ?? 0.55),
        opacity: 1,
        transparent: false,
      };
    }
    case "multi_selected": {
      const profile = dentalMaterialProfiles.enamelSelected;
      return {
        role,
        color: profileColor(profile.color, 0xf4e6c8),
        emissive: profileColor(profile.emissive, 0x3d2a12),
        emissiveIntensity: Number(profile.emissiveIntensity ?? 0.12) * 0.7,
        roughness: Number(profile.roughness ?? 0.36),
        envMapIntensity: Number(profile.envMapIntensity ?? 0.55),
        opacity: 1,
        transparent: false,
      };
    }
    case "hovered":
      return {
        role,
        color: baseColor,
        emissive: 0x2a2418,
        emissiveIntensity: 0.05,
        roughness: Number(base.roughness ?? 0.42),
        envMapIntensity: Number(base.envMapIntensity ?? 0.48),
        opacity: 1,
        transparent: false,
      };
    case "validation_error":
      return {
        role,
        color: baseColor,
        emissive: 0x6a2420,
        emissiveIntensity: 0.14,
        roughness: Number(base.roughness ?? 0.42),
        envMapIntensity: Number(base.envMapIntensity ?? 0.48),
        opacity: 1,
        transparent: false,
      };
    case "validation_warning":
      return {
        role,
        color: baseColor,
        emissive: 0x5a4014,
        emissiveIntensity: 0.1,
        roughness: Number(base.roughness ?? 0.42),
        envMapIntensity: Number(base.envMapIntensity ?? 0.48),
        opacity: 1,
        transparent: false,
      };
    case "treatment_target": {
      const profile = dentalMaterialProfiles.enamelTarget;
      return {
        role,
        color: profileColor(profile.color, 0xd5e2ea),
        emissive: 0x000000,
        emissiveIntensity: 0,
        roughness: Number(profile.roughness ?? 0.5),
        envMapIntensity: Number(profile.envMapIntensity ?? 0.32),
        opacity: Number(profile.opacity ?? 0.68),
        transparent: true,
      };
    }
    case "requires_review":
      // Soft cool edge — distinct from verified/selected warmth; not an error claim.
      return {
        role,
        color: baseColor,
        emissive: 0x1a3040,
        emissiveIntensity: 0.08,
        roughness: Number(base.roughness ?? 0.3),
        envMapIntensity: Number(base.envMapIntensity ?? 1),
        opacity: 1,
        transparent: false,
      };
    case "unavailable":
      return {
        role,
        color: 0xb8b2a8,
        emissive: 0x000000,
        emissiveIntensity: 0,
        roughness: 0.55,
        envMapIntensity: 0.6,
        opacity: 0.85,
        transparent: true,
      };
    case "hidden":
      return {
        role,
        color: baseColor,
        emissive: 0x000000,
        emissiveIntensity: 0,
        roughness: 0.4,
        envMapIntensity: 0.5,
        opacity: 0,
        transparent: true,
      };
    default:
      return {
        role: "normal",
        color: baseColor,
        emissive: 0x000000,
        emissiveIntensity: 0,
        roughness: Number(base.roughness ?? 0.28),
        envMapIntensity: Number(base.envMapIntensity ?? 1),
        opacity: 1,
        transparent: false,
      };
  }
}
