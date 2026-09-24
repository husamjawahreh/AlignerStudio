import { useState } from "react";
import type { ToothSelectionState } from "@alignerstudio/types";
import type { ReviewToothMesh } from "../review/types";

const EMPTY_SELECTION: ToothSelectionState = {
  selectedToothRef: null,
  semanticIdentifier: null,
  fdiNumber: null,
  arch: null,
  confidence: null,
};

export function useToothSelection(teeth: readonly ReviewToothMesh[]) {
  const [selection, setSelection] = useState<ToothSelectionState>(EMPTY_SELECTION);

  function selectTooth(toothRef: string): void {
    const tooth = teeth.find(
      (item) => (item.toothRef ?? `instance:${item.instanceId}`) === toothRef,
    );
    setSelection(
      tooth
        ? {
            selectedToothRef: toothRef,
            semanticIdentifier: tooth.semanticLabel ?? null,
            fdiNumber: tooth.fdiNumber,
            arch: tooth.arch,
            confidence: tooth.confidence,
          }
        : EMPTY_SELECTION,
    );
  }

  return { selection, selectTooth, clearSelection: () => setSelection(EMPTY_SELECTION) };
}