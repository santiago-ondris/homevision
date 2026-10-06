import { useEffect, useReducer, useRef } from "react";

import DocumentViewer from "./components/DocumentViewer";
import Header from "./components/Header";
import Inspector from "./components/Inspector";
import type { Sample } from "./components/SamplePicker";
import { detect, networkErrorMessage } from "./lib/api";
import { maximumUploadBytes, megabytes, summary } from "./lib/format";
import { initialState, reducer, type ImagePreview } from "./lib/state";
import "./styles/base.css";

const copiedDurationMs = 2_000;

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const fileInput = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const copyTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const imageUrl = state.image?.url;

  useEffect(
    () => () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    },
    [imageUrl],
  );
  useEffect(
    () => () => {
      request.current?.abort();
      if (copyTimeout.current !== null) clearTimeout(copyTimeout.current);
    },
    [],
  );

  function beginRequest() {
    request.current?.abort();
    if (copyTimeout.current !== null) clearTimeout(copyTimeout.current);
    const controller = new AbortController();
    request.current = controller;
    dispatch({ type: "start", image: null });
    return controller;
  }

  async function sendFile(file: File, controller: AbortController) {
    if (controller.signal.aborted) return;
    const image: ImagePreview = {
      url: URL.createObjectURL(file),
      name: file.name,
      width: 0,
      height: 0,
    };
    dispatch({ type: "start", image });
    if (file.type !== "image/png" && file.type !== "image/jpeg") {
      dispatch({ type: "error", message: "This file is not a PNG or JPEG image." });
      return;
    }
    if (file.size > maximumUploadBytes) {
      dispatch({
        type: "error",
        message: `The file is ${megabytes(file.size)} MB. The limit is 20 MB.`,
      });
      return;
    }
    const result = await detect(file, controller.signal);
    if (!controller.signal.aborted) dispatch({ type: "result", result });
  }

  function chooseFile(file: File) {
    void sendFile(file, beginRequest());
  }

  async function chooseSample(sample: Sample) {
    const controller = beginRequest();
    try {
      const response = await fetch(`/samples/${sample.filename}`, { signal: controller.signal });
      if (!response.ok) {
        if (!controller.signal.aborted) dispatch({ type: "error", message: networkErrorMessage });
        return;
      }
      const blob = await response.blob();
      const type = sample.filename.endsWith(".jpg") ? "image/jpeg" : "image/png";
      await sendFile(new File([blob], sample.filename, { type }), controller);
    } catch {
      if (!controller.signal.aborted) dispatch({ type: "error", message: networkErrorMessage });
    }
  }

  async function copyJson() {
    if (state.status !== "success") return;
    const controller = request.current;
    if (copyTimeout.current !== null) clearTimeout(copyTimeout.current);
    try {
      await navigator.clipboard.writeText(JSON.stringify({ boxes: state.result.boxes }, null, 2));
      if (controller?.signal.aborted) return;
      dispatch({ type: "copy", copied: true });
      copyTimeout.current = setTimeout(
        () => dispatch({ type: "copy", copied: false }),
        copiedDurationMs,
      );
    } catch {
      if (!controller?.signal.aborted)
        dispatch({
          type: "copy",
          copied: false,
          error: "Could not copy the response. Select the JSON and copy it manually.",
        });
    }
  }

  const interaction = {
    selected: state.selection?.index ?? null,
    hovered: state.hovered,
    focused: state.focused,
    onHighlight: (index: number | null, source: "pointer" | "keyboard") =>
      dispatch({ type: "highlight", index, source }),
    onSelect: (index: number, source: "row" | "rect") =>
      dispatch({ type: "select", index, source }),
  };
  const announcement =
    state.status === "loading"
      ? "Detecting…"
      : state.status === "error"
        ? state.message
        : state.status === "success"
          ? summary(state.result.boxes, state.result.durationMs)
          : "";
  const openFilePicker = () => fileInput.current?.click();

  return (
    <div
      className="app"
      onKeyDown={(event) => {
        if (event.key === "Escape") dispatch({ type: "clear_selection" });
      }}
    >
      <Header
        onChoose={openFilePicker}
        onSample={(sample) => {
          void chooseSample(sample);
        }}
      />
      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg"
        hidden
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) chooseFile(file);
        }}
      />
      <div className="live-region" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
      <main>
        <DocumentViewer
          image={state.image}
          boxes={state.status === "success" ? state.result.boxes : []}
          loading={state.status === "loading"}
          zoom={state.zoom}
          selection={state.selection}
          interaction={interaction}
          onZoom={() => dispatch({ type: "zoom" })}
          onChoose={openFilePicker}
          onFile={chooseFile}
          onSample={(sample) => {
            void chooseSample(sample);
          }}
          onImageLoaded={(image) =>
            dispatch({
              type: "image_loaded",
              url: image.url,
              width: image.width,
              height: image.height,
            })
          }
          onImageFailed={(url) => dispatch({ type: "image_failed", url })}
        />
        <Inspector
          state={state}
          interaction={interaction}
          onTab={(tab) => dispatch({ type: "tab", tab })}
          onChoose={openFilePicker}
          onCopy={() => {
            void copyJson();
          }}
        />
      </main>
    </div>
  );
}
