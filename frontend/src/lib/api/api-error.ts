export type ApiErrorKind = "http" | "network" | "unknown";

export class ApiClientError extends Error {
  kind: ApiErrorKind;
  status?: number;
  detail?: string;
  userMessage?: string;
  data?: unknown;

  constructor(args: {
    message: string;
    kind: ApiErrorKind;
    status?: number;
    detail?: string;
    userMessage?: string;
    data?: unknown;
  }) {
    super(args.message);
    this.name = "ApiClientError";
    this.kind = args.kind;
    this.status = args.status;
    this.detail = args.detail;
    this.userMessage = args.userMessage;
    this.data = args.data;
  }
}

