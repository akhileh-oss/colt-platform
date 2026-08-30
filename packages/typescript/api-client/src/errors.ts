/**
 * The shared error envelope shape (CLAUDE.md §25.4), mirrored from `colt_api.errors` so a
 * caller can narrow a failed `openapi-fetch` response without re-deriving the contract.
 *
 * This type is hand-written, not generated: FastAPI documents `ErrorResponse` as the schema for
 * specific status codes it happens to annotate, but every endpoint can in practice fail with
 * this shape (validation, auth, rate limiting, ...). Duplicating that generically here is the
 * pragmatic middle ground between "not generated" and "generated but attached to the wrong
 * places in the schema."
 */

export const ERROR_CODES = [
  "VALIDATION_ERROR",
  "AUTHENTICATION_ERROR",
  "AUTHORIZATION_ERROR",
  "NOT_FOUND",
  "CONFLICT",
  "RATE_LIMITED",
  "PROVIDER_UNAVAILABLE",
  "PROVIDER_REJECTED",
  "TIMEOUT",
  "DEPENDENCY_FAILURE",
  "INTERNAL_ERROR",
  "POLICY_DENIED",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export interface ErrorDetail {
  code: ErrorCode;
  message: string;
  request_id: string | null;
  details: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

/** Narrow an unknown value from a failed request to the Colt error envelope. */
export function isColtErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    "message" in error &&
    typeof (error as { code: unknown }).code === "string"
  );
}
