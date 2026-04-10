import { describe, expect, it } from "vitest";

import { ApiClientError } from "@/lib/api/api-error";
import { getUserFacingErrorMessage } from "./errors";

describe("getUserFacingErrorMessage", () => {
  it("maps missing backend api key to a readable localized message", () => {
    const error = new ApiClientError({
      message: "HTTP 401: Missing or invalid API key.",
      kind: "http",
      status: 401,
      detail: "Missing or invalid API key."
    });

    expect(getUserFacingErrorMessage(error, { isChinese: true, context: "backend" })).toContain("后端 API Key");
    expect(getUserFacingErrorMessage(error, { isChinese: false, context: "backend" })).toContain("backend API key");
  });

  it("maps forbidden role failures to a read-only/admin-only hint", () => {
    const error = new ApiClientError({
      message: "HTTP 403: Insufficient role for this operation.",
      kind: "http",
      status: 403,
      detail: "Insufficient role for this operation. Requires one of: admin"
    });

    expect(getUserFacingErrorMessage(error, { isChinese: true, context: "backend" })).toContain("权限不足");
    expect(getUserFacingErrorMessage(error, { isChinese: false, context: "backend" })).toContain("does not allow");
  });
});

