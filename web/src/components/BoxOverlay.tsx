import type { Box } from "../lib/api";
import { accessibleName } from "../lib/format";

export interface BoxInteraction {
  selected: number | null;
  hovered: number | null;
  focused: number | null;
  onHighlight: (index: number | null, source: "pointer" | "keyboard") => void;
  onSelect: (index: number, source: "row" | "rect") => void;
}

interface Props {
  boxes: Box[];
  width: number;
  height: number;
  interaction: BoxInteraction;
}

export default function BoxOverlay({ boxes, width, height, interaction }: Props) {
  return (
    <svg
      className="box-overlay"
      viewBox={`0 0 ${width} ${height}`}
      aria-label="Detected checkboxes"
    >
      {boxes.map((box, index) => {
        const [x1, y1, x2, y2] = box.bbox;
        const highlighted = interaction.hovered === index || interaction.focused === index;
        return (
          <rect
            key={index}
            data-box-index={index}
            x={x1}
            y={y1}
            width={x2 - x1}
            height={y2 - y1}
            vectorEffect="non-scaling-stroke"
            className={`box ${box.is_checked ? "checked" : "empty"}${highlighted ? " highlighted" : ""}${interaction.selected === index ? " selected" : ""}`}
            tabIndex={0}
            role="button"
            aria-label={accessibleName(box, index)}
            aria-pressed={interaction.selected === index}
            onMouseEnter={() => interaction.onHighlight(index, "pointer")}
            onMouseLeave={() => interaction.onHighlight(null, "pointer")}
            onFocus={() => interaction.onHighlight(index, "keyboard")}
            onBlur={() => interaction.onHighlight(null, "keyboard")}
            onClick={() => interaction.onSelect(index, "rect")}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                interaction.onSelect(index, "rect");
              }
            }}
          />
        );
      })}
    </svg>
  );
}
