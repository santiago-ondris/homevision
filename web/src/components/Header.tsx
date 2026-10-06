import SamplePicker, { type Sample } from "./SamplePicker";

interface Props {
  onChoose: () => void;
  onSample: (sample: Sample) => void;
}

export default function Header({ onChoose, onSample }: Props) {
  return (
    <header>
      <h1>Checkbox detection</h1>
      <SamplePicker onChoose={onSample} />
      <button type="button" onClick={onChoose}>
        Choose image
      </button>
    </header>
  );
}
