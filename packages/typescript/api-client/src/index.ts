/**
 * Typed Colt API client.
 *
 * `src/generated/` is produced from the FastAPI OpenAPI schema by `pnpm generate` and is never
 * edited by hand (CLAUDE.md §25.3, §44, ADR-0004). Hand-written helpers live in the sibling
 * files re-exported here.
 */

export { createColtClient, type ColtClient, type CreateColtClientOptions } from "./client";
export {
  ERROR_CODES,
  isColtErrorResponse,
  type ErrorCode,
  type ErrorDetail,
  type ErrorResponse,
} from "./errors";

export const VERSION = "0.1.0";
