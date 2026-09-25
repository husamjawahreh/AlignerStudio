import { useCallback, useRef, useState } from "react";
import type { ToothSelectionState } from "@alignerstudio/types";
import type { ReviewToothMesh } from "../review/types";
import { findToothByKey, reviewToothKey } from "./toothKey";
import {
  preserveSelectionAcrossTeeth,
  selectionStateFromIdentity,
  semanticIdentityFromTooth,
} from "./workspace";

const EMPTY_SELECTION: ToothSelectionState = {
  selectedToothRef: null,
  semanticIdentifier: null,
  fdiNumber: null,
  arch: null,
  confidence: null,
};

/**
 * Selection state owned by React; scene objects are not the source of truth.
 * Multi-selection is a foundation (additive keys) for later CAD tools.
 */
export function useToothSelection(teeth: readonly ReviewToothMesh[]) {
  const [selection, setSelection] = useState<ToothSelectionState>(EMPTY_SELECTION);
  const [multiSelectedKeys, setMultiSelectedKeys] = useState<readonly string[]>([]);
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  const selectTooth = useCallback(
    (toothRef: string, options?: { additive?: boolean }) => {
      const tooth = findToothByKey(teeth, toothRef);
      if (!tooth) {
        setSelection(EMPTY_SELECTION);
        if (!options?.additive) setMultiSelectedKeys([]);
        return;
      }
      const identity = semanticIdentityFromTooth(tooth);
      const next = selectionStateFromIdentity(identity);
      next.confidence = tooth.confidence;
      if (options?.additive) {
        setMultiSelectedKeys((current) => {
          const key = identity.key;
          const seeded =
            current.length === 0 && selectionRef.current.selectedToothRef
              ? [selectionRef.current.selectedToothRef]
              : [...current];
          if (seeded.includes(key)) return seeded.filter((item) => item !== key);
          return [...seeded, key];
        });
        setSelection(next);
        return;
      }
      setMultiSelectedKeys([identity.key]);
      setSelection(next);
    },
    [teeth],
  );

  const clearSelection = useCallback(() => {
    setSelection(EMPTY_SELECTION);
    setMultiSelectedKeys([]);
  }, []);

  /** Re-resolve selection after stage/mesh reload using persistent tooth_ref. */
  const preserveAcrossTeeth = useCallback((nextTeeth: readonly ReviewToothMesh[]) => {
    setSelection((current) => {
      const preserved = preserveSelectionAcrossTeeth(current.selectedToothRef, nextTeeth);
      if (!preserved) {
        if (current.selectedToothRef == null) return current;
        return EMPTY_SELECTION;
      }
      const next = selectionStateFromIdentity(preserved);
      const match = findToothByKey(nextTeeth, preserved.key);
      next.confidence = match?.confidence ?? null;
      if (
        current.selectedToothRef === next.selectedToothRef &&
        current.fdiNumber === next.fdiNumber &&
        current.arch === next.arch &&
        current.confidence === next.confidence
      ) {
        return current;
      }
      return next;
    });
    setMultiSelectedKeys((current) =>
      current.filter((key) => findToothByKey(nextTeeth, key) != null),
    );
  }, []);

  return {
    selection,
    selectTooth,
    clearSelection,
    multiSelectedKeys,
    preserveAcrossTeeth,
    selectedKey: selection.selectedToothRef,
    /** Convenience: resolve current tooth from the live teeth list. */
    resolveSelectedTooth: () =>
      selection.selectedToothRef
        ? findToothByKey(teeth, selection.selectedToothRef)
        : null,
    reviewToothKey,
  };
}
