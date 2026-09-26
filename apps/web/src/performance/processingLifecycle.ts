/** Processing poll and completion-load rules. Navigation does not start work. */

export function shouldPollProcessing(stageStatus: string | null | undefined): boolean {
  return stageStatus === "PROCESSING";
}

/**
 * The completion load may start once per job.
 * A second poll of the same completed job must not fetch treatment again.
 */
export function claimTerminalLoad(claimedJobId: { current: string | null }, jobId: string): boolean {
  if (!jobId || claimedJobId.current === jobId) return false;
  claimedJobId.current = jobId;
  return true;
}
