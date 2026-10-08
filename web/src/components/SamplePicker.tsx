import { publicForms } from "./publicForms";
import type { KnownIssue } from "../lib/state";

export interface Sample {
  filename: string;
  label: string;
  knownIssues?: KnownIssue[];
}

const samples: Sample[] = [
  {
    filename: "sample1.png",
    label: "Appraisal report",
    knownIssues: [
      {
        text: "False detection: the gap between two neighboring boxes.",
        bbox: [433, 2756, 490, 2808],
      },
    ],
  },
  {
    filename: "sample2.jpg",
    label: "Neighborhood section (scan)",
    knownIssues: [
      { text: "Box not found: its border is very faint.", bbox: [281, 186, 307, 209] },
      {
        text: "Box not found: a scribbled-out X breaks its border.",
        bbox: [196, 611, 220, 636],
      },
      {
        text: "Empty box read as checked: a pen stroke crosses it.",
        bbox: [713, 491, 737, 515],
      },
    ],
  },
  { filename: "sample3.png", label: "Market conditions addendum" },
  {
    filename: "sample4.png",
    label: "Manufactured home report",
    knownIssues: [
      {
        text: "Box not found: a red watermark covers its corner.",
        bbox: [1503, 1380, 1534, 1410],
      },
    ],
  },
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
  onMoreForms?: () => void;
}

export default function SamplePicker({ onChoose, large = false, onMoreForms }: Props) {
  return (
    <>
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
        {!large && (
          <button type="button" aria-haspopup="dialog" onClick={onMoreForms}>
            More forms
          </button>
        )}
      </div>
      {large && (
        <div className="public-forms">
          <p className="public-forms-caption">Public forms used in the evaluation</p>
          <div className="public-forms-buttons">
            {publicForms.map((sample) => (
              <button key={sample.filename} type="button" onClick={() => onChoose(sample)}>
                {sample.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
