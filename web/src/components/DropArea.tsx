import { idleHint } from "../lib/format";
import SamplePicker, { type Sample } from "./SamplePicker";

interface Props {
  onChoose: () => void;
  onSample: (sample: Sample) => void;
}

export default function DropArea({ onChoose, onSample }: Props) {
  return (
    <div className="drop-area">
      <p className="viewer-caption">Choose an image, or try a sample</p>
      <div className="empty-actions">
        <button type="button" className="primary-button" aria-label={idleHint} onClick={onChoose}>
          Choose image <span aria-hidden="true">→</span>
        </button>
        <span className="drop-hint">or drop a PNG or JPEG anywhere</span>
      </div>
      <SamplePicker large onChoose={onSample} />
    </div>
  );
}
