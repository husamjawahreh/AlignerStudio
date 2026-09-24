import { useState } from "react";
import type { ToothSelectionState } from "@alignerstudio/types";
import type { ReviewToothMesh } from "../review/types";
import { findToothByKey, reviewToothKey } from "./toothKey";

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
    const tooth = findToothByKey(teeth, toothRef);
    setSelection(
      tooth
        ? {
            selectedToothRef: reviewToothKey(tooth),
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
