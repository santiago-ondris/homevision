import type { DetectResult } from "./api";

export type Tab = "boxes" | "json";
export type Zoom = "fit" | "actual";
export interface Selection {
  index: number;
  source: "row" | "rect";
}
export interface ImagePreview {
  knownIssues?: KnownIssue[];
  url: string;
  name: string;
  width: number;
  height: number;
}

export interface KnownIssue {
  text: string;
  bbox: [number, number, number, number];
}

interface ViewState {
  image: ImagePreview | null;
  zoom: Zoom;
  tab: Tab;
  selection: Selection | null;
  hovered: number | null;
  focused: number | null;
  copied: boolean;
  copyError: string | null;
}

export type State = ViewState &
  (
    | { status: "idle" }
    | { status: "loading" }
    | { status: "success"; result: Extract<DetectResult, { ok: true }> }
    | { status: "error"; message: string; requestId: string | null }
  );

export type Action =
  | { type: "start"; image: ImagePreview | null }
  | { type: "result"; result: DetectResult }
  | { type: "error"; message: string }
  | { type: "image_loaded"; url: string; width: number; height: number }
  | { type: "image_failed"; url: string }
  | { type: "zoom" }
  | { type: "tab"; tab: Tab }
  | { type: "highlight"; index: number | null; source: "pointer" | "keyboard" }
  | { type: "select"; index: number; source: "row" | "rect" }
  | { type: "clear_selection" }
  | { type: "copy"; copied: boolean; error?: string };

export const initialState: State = {
  status: "idle",
  image: null,
  zoom: "fit",
  tab: "boxes",
  selection: null,
  hovered: null,
  focused: null,
  copied: false,
  copyError: null,
};

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "start":
      return { ...initialState, status: "loading", image: action.image };
    case "result":
      if (action.result.ok) return { ...state, status: "success", result: action.result };
      return {
        ...state,
        status: "error",
        message: action.result.message,
        requestId: action.result.requestId,
      };
    case "error":
      return { ...state, status: "error", message: action.message, requestId: null };
    case "image_loaded":
      return state.image?.url === action.url
        ? { ...state, image: { ...state.image, width: action.width, height: action.height } }
        : state;
    case "image_failed":
      return state.image?.url === action.url ? { ...state, image: null } : state;
    case "zoom":
      return { ...state, zoom: state.zoom === "fit" ? "actual" : "fit" };
    case "tab":
      return { ...state, tab: action.tab };
    case "highlight":
      return action.source === "pointer"
        ? { ...state, hovered: action.index }
        : { ...state, focused: action.index };
    case "select":
      return {
        ...state,
        selection: { index: action.index, source: action.source },
        tab: action.source === "rect" ? "boxes" : state.tab,
      };
    case "clear_selection":
      return { ...state, selection: null, hovered: null, focused: null };
    case "copy":
      return { ...state, copied: action.copied, copyError: action.error ?? null };
  }
}
