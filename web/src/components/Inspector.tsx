import { useRef } from "react";

import type { State, Tab } from "../lib/state";
import type { BoxInteraction } from "./BoxOverlay";
import BoxList from "./BoxList";
import JsonView from "./JsonView";
import Footer from "./Footer";
import Readout from "./Readout";

interface Props {
  state: State;
  interaction: BoxInteraction;
  onTab: (tab: Tab) => void;
  onChoose: () => void;
  onCopy: () => void;
}

export default function Inspector({ state, interaction, onTab, onChoose, onCopy }: Props) {
  const boxesTab = useRef<HTMLButtonElement>(null);
  const jsonTab = useRef<HTMLButtonElement>(null);
  if (state.status === "idle") return null;
  if (state.status === "loading")
    return (
      <aside className="inspector">
        <p className="inspector-message">Detecting…</p>
        <Footer />
      </aside>
    );
  if (state.status === "error") {
    return (
      <aside className="inspector">
        <div className="error-block">
          <p className="error-label">Error</p>
          <p>{state.message}</p>
          {state.requestId && (
            <p className="request-id">
              <span className="request-label">Request ID</span>: <code>{state.requestId}</code>
            </p>
          )}
          <button type="button" onClick={onChoose}>
            Try another image
          </button>
        </div>
        <Footer />
      </aside>
    );
  }

  function moveTab(key: string) {
    let tab: Tab;
    if (key === "ArrowLeft" || key === "ArrowRight") tab = state.tab === "boxes" ? "json" : "boxes";
    else if (key === "Home") tab = "boxes";
    else if (key === "End") tab = "json";
    else return false;
    onTab(tab);
    (tab === "boxes" ? boxesTab : jsonTab).current?.focus();
    return true;
  }

  return (
    <aside className="inspector">
      <Readout boxes={state.result.boxes} durationMs={state.result.durationMs} />
      <div
        role="tablist"
        className="inspector-tabs"
        aria-label="Detection results"
        onKeyDown={(event) => {
          if (moveTab(event.key)) event.preventDefault();
        }}
      >
        <button
          type="button"
          id="boxes-tab"
          role="tab"
          ref={boxesTab}
          aria-selected={state.tab === "boxes"}
          aria-controls="boxes-panel"
          tabIndex={state.tab === "boxes" ? 0 : -1}
          onClick={() => onTab("boxes")}
        >
          Boxes
        </button>
        <button
          type="button"
          id="json-tab"
          role="tab"
          ref={jsonTab}
          aria-selected={state.tab === "json"}
          aria-controls="json-panel"
          tabIndex={state.tab === "json" ? 0 : -1}
          onClick={() => onTab("json")}
        >
          JSON
        </button>
      </div>
      <div
        id="boxes-panel"
        role="tabpanel"
        aria-labelledby="boxes-tab"
        hidden={state.tab !== "boxes"}
        tabIndex={0}
        className="inspector-panel"
      >
        {state.tab === "boxes" && (
          <BoxList
            boxes={state.result.boxes}
            interaction={interaction}
            selection={state.selection}
          />
        )}
      </div>
      <div
        id="json-panel"
        role="tabpanel"
        aria-labelledby="json-tab"
        hidden={state.tab !== "json"}
        tabIndex={0}
        className="inspector-panel"
      >
        {state.tab === "json" && (
          <JsonView
            json={JSON.stringify({ boxes: state.result.boxes }, null, 2)}
            copied={state.copied}
            error={state.copyError}
            onCopy={onCopy}
          />
        )}
      </div>
      <Footer />
    </aside>
  );
}
