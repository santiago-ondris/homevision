import SamplePicker, { type Sample } from "./SamplePicker";

interface Props {
  idle: boolean;
  onChoose: () => void;
  onSample: (sample: Sample) => void;
  onMoreForms: () => void;
}

export default function Header({ idle, onChoose, onSample, onMoreForms }: Props) {
  return (
    <header className="page-header">
      <div className="wordmark">
        <span className="header-mark" aria-hidden="true" />
        <h1>Checkbox detection</h1>
      </div>
      {!idle && <SamplePicker onChoose={onSample} onMoreForms={onMoreForms} />}
      <button type="button" className="primary-button" onClick={onChoose}>
        Choose image <span aria-hidden="true">→</span>
      </button>
    </header>
  );
}
