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

const sampleDetails = [
  "2550 × 4200 · PNG",
  "1586 × 846 · JPEG",
  "2550 × 4200 · PNG",
  "2550 × 3301 · PNG",
];

interface Props {
  onChoose: (sample: Sample) => void;
  large?: boolean;
}

export default function SamplePicker({ onChoose, large = false }: Props) {
  return (
    <div className={large ? "sample-picker sample-picker-large" : "sample-picker"}>
      {samples.map((sample, index) => (
        <button
          key={sample.filename}
          type="button"
          aria-label={sample.label}
          onClick={() => onChoose(sample)}
        >
          {large ? (
            <>
              <span className="sample-well">
                <img src={`/samples/${sample.filename}`} alt="" />
              </span>
              <span className="sample-meta">
                <span className="sample-name">{sample.label}</span>
                <span className="sample-details" aria-hidden="true">
                  {sampleDetails[index]}
                </span>
              </span>
            </>
          ) : (
            <span>{sample.label}</span>
          )}
        </button>
      ))}
    </div>
  );
}
