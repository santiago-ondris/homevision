export interface Sample {
  filename: string;
  label: string;
}

const samples: Sample[] = [
  { filename: "sample1.png", label: "Appraisal report" },
  { filename: "sample2.jpg", label: "Neighborhood section (scan)" },
  { filename: "sample3.png", label: "Market conditions addendum" },
  { filename: "sample4.png", label: "Manufactured home report" },
];

interface Props {
  onChoose: (sample: Sample) => void;
  large?: boolean;
}

export default function SamplePicker({ onChoose, large = false }: Props) {
  return (
    <div className={large ? "sample-picker sample-picker-large" : "sample-picker"}>
      {samples.map((sample) => (
        <button key={sample.filename} type="button" onClick={() => onChoose(sample)}>
          {large && <img src={`/samples/${sample.filename}`} alt="" />}
          <span>{sample.label}</span>
        </button>
      ))}
    </div>
  );
}
