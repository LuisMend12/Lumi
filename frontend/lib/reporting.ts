// Plain-language wording for report and vote outcomes. Unverified and pending
// reports are never described as fact (docs/team/api-contract.md).
import type { ReportOutcome, VoteOutcome } from "./reports-api";

export const REPORT_OUTCOME_TEXT: Record<ReportOutcome, string> = {
  status_changed: "Sidewalk marked blocked. Routes now avoid it.",
  vote_recorded: "Already marked blocked. Thanks for confirming.",
  unverified: "We couldn't confirm a blockage in this photo. It's shown as unverified and won't change routes.",
  pending: "Your photo is under review. It won't change routes until it's checked.",
};

export const VOTE_OUTCOME_TEXT: Record<VoteOutcome, string> = {
  status_changed: "Thanks. Enough people agreed, so this sidewalk's status changed.",
  vote_recorded: "Thanks. Your answer was recorded.",
  photo_required: "You've reported several blocked sidewalks recently. Please add a photo for this one.",
};
