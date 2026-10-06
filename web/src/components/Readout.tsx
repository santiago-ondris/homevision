import type { Box } from "../lib/api";

interface Props {
  boxes: Box[];
  durationMs: number | null;
}

export default function Readout({ boxes, durationMs }: Props) {
  const checked = boxes.filter((box) => box.is_checked).length;
  const cells = [
    { label: boxes.length === 1 ? "Box" : "Boxes", value: boxes.length },
    { label: "Checked", value: checked },
    { label: "Empty", value: boxes.length - checked },
  ];
  if (durationMs !== null) cells.push({ label: "ms", value: Math.round(durationMs) });

  return (
    <div className="readout" aria-hidden="true">
      {cells.map(({ label, value }) => (
        <div className="readout-cell" key={label}>
          <span className="readout-number">{value}</span>
          <span className="readout-label">{label}</span>
        </div>
      ))}
    </div>
  );
}
