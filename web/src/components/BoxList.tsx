import { useEffect, useRef } from "react";

import type { Box } from "../lib/api";
import { emptyResultMessage } from "../lib/format";
import type { Selection } from "../lib/state";
import type { BoxInteraction } from "./BoxOverlay";

interface Props {
  boxes: Box[];
  interaction: BoxInteraction;
  selection: Selection | null;
}

export default function BoxList({ boxes, interaction, selection }: Props) {
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (selection?.source !== "rect") return;
    list.current?.querySelector(`[data-box-index="${selection.index}"]`)?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }, [selection]);

  return (
    <div className="box-list" ref={list}>
      {boxes.length === 0 && <p>{emptyResultMessage}</p>}
      {boxes.map((box, index) => {
        const highlighted = interaction.hovered === index || interaction.focused === index;
        return (
          <button
            type="button"
            key={index}
            data-box-index={index}
            className={`box-row${highlighted ? " highlighted" : ""}${interaction.selected === index ? " selected" : ""}`}
            aria-pressed={interaction.selected === index}
            onMouseEnter={() => interaction.onHighlight(index, "pointer")}
            onMouseLeave={() => interaction.onHighlight(null, "pointer")}
            onFocus={() => interaction.onHighlight(index, "keyboard")}
            onBlur={() => interaction.onHighlight(null, "keyboard")}
            onClick={() => interaction.onSelect(index, "row")}
          >
            <span>{index + 1}</span>
            <span>{box.is_checked ? "checked" : "empty"}</span>
            <span>[{box.bbox.join(", ")}]</span>
          </button>
        );
      })}
    </div>
  );
}
