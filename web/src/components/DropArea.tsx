import { idleHint } from "../lib/format";
import SamplePicker, { type Sample } from "./SamplePicker";

interface Props {
  onChoose: () => void;
  onSample: (sample: Sample) => void;
}

export default function DropArea({ onChoose, onSample }: Props) {
  return (
    <div className="drop-area">
      <button type="button" className="drop-button" onClick={onChoose}>
        {idleHint}
      </button>
      <SamplePicker large onChoose={onSample} />
    </div>
  );
}
