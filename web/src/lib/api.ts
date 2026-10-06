import { API_URL } from "./config";

export interface Box {
  bbox: [number, number, number, number];
  is_checked: boolean;
}

const errorCodes = [
  "invalid_request",
  "not_found",
  "method_not_allowed",
  "file_too_large",
  "unsupported_media_type",
  "invalid_image",
  "internal_error",
  "overloaded",
  "detector_unavailable",
  "detector_timeout",
] as const;

type ErrorCode = (typeof errorCodes)[number];
export type DetectResult =
  | { ok: true; boxes: Box[]; durationMs: number | null; requestId: string | null }
  | {
      ok: false;
      code: ErrorCode | "network_error" | "bad_response";
      message: string;
      requestId: string | null;
    };

const responseTimeoutMs = 60_000;
export const networkErrorMessage =
  "Could not reach the server. Check your connection and try again.";
const badResponseMessage = "The server sent a response this page could not read.";
const coordinateCount = 4;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isBox(value: unknown): value is Box {
  return (
    isRecord(value) &&
    Object.keys(value).length === 2 &&
    Array.isArray(value.bbox) &&
    value.bbox.length === coordinateCount &&
    value.bbox.every((coordinate: unknown) => Number.isInteger(coordinate)) &&
    typeof value.is_checked === "boolean"
  );
}

function isErrorCode(value: unknown): value is ErrorCode {
  return errorCodes.some((code) => code === value);
}

function duration(header: string | null): number | null {
  const match = header?.match(/(?:^|,)\s*total\s*;\s*dur=([\d.]+)(?:\s|,|$)/);
  if (!match) return null;
  const milliseconds = Number(match[1]);
  return Number.isFinite(milliseconds) ? milliseconds : null;
}

async function readResponse(response: Response): Promise<DetectResult> {
  const requestId = response.headers.get("X-Request-Id");
  const unreadable: DetectResult = {
    ok: false,
    code: "bad_response",
    message: badResponseMessage,
    requestId,
  };
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return unreadable;
  }
  if (!isRecord(body)) return unreadable;
  if (response.status === 200) {
    if (Object.keys(body).length !== 1 || !Array.isArray(body.boxes) || !body.boxes.every(isBox)) {
      return unreadable;
    }
    return {
      ok: true,
      boxes: body.boxes,
      durationMs: duration(response.headers.get("Server-Timing")),
      requestId,
    };
  }
  if (!response.ok && isRecord(body.error)) {
    const { code, message } = body.error;
    if (isErrorCode(code) && typeof message === "string") {
      return { ok: false, code, message, requestId };
    }
  }
  return unreadable;
}

export async function detect(file: File, signal: AbortSignal): Promise<DetectResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), responseTimeoutMs);
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch(`${API_URL}/detect`, {
      method: "POST",
      body: form,
      signal: AbortSignal.any([signal, controller.signal]),
    });
    clearTimeout(timeout);
    return await readResponse(response);
  } catch {
    return { ok: false, code: "network_error", message: networkErrorMessage, requestId: null };
  } finally {
    clearTimeout(timeout);
  }
}
