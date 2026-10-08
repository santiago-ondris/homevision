import type { RefObject } from "react";

import { publicForms } from "./publicForms";
import type { Sample } from "./SamplePicker";

interface Props {
  dialog: RefObject<HTMLDialogElement | null>;
  onChoose: (sample: Sample) => void;
}

export default function PublicFormsDialog({ dialog, onChoose }: Props) {
  return (
    <dialog
      ref={dialog}
      className="public-forms-dialog"
      aria-labelledby="public-forms-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") event.stopPropagation();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          event.currentTarget.close();
      }}
    >
      <div className="public-forms-heading">
        <h2 id="public-forms-title">Public forms used in the evaluation</h2>
        <button type="button" onClick={() => dialog.current?.close()}>
          Close
        </button>
      </div>
      <div className="public-forms-list">
        {publicForms.map((sample) => (
          <button
            key={sample.filename}
            type="button"
            onClick={() => {
              dialog.current?.close();
              onChoose(sample);
            }}
          >
            <span>{sample.label}</span>
            <span className="sample-details">{sample.details}</span>
          </button>
        ))}
      </div>
    </dialog>
  );
}
