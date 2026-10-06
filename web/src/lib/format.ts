import type { Box } from "./api";

export const maximumUploadBytes = 20 * 1024 * 1024;
const bytesPerMegabyte = 1024 * 1024;

export function megabytes(bytes: number): string {
  return (bytes / bytesPerMegabyte).toFixed(2);
}

export function summary(boxes: Box[], durationMs: number | null): string {
  const checked = boxes.filter((box) => box.is_checked).length;
  const count = `${boxes.length} ${boxes.length === 1 ? "box" : "boxes"}`;
  const counts = `${count} · ${checked} checked · ${boxes.length - checked} empty`;
  return durationMs === null ? counts : `${counts} · ${Math.round(durationMs)} ms`;
}

export function accessibleName(box: Box, index: number): string {
  return `Checkbox ${index + 1}, ${box.is_checked ? "checked" : "empty"}, at ${box.bbox[0]}, ${box.bbox[1]}`;
}

export const idleHint = "Choose an image of a form, or try one of the samples.";
export const emptyResultMessage = "No checkboxes found in this image.";
