import { useEffect, useRef } from "react";

import type { Box } from "../lib/api";
import type { ImagePreview, Selection, Zoom } from "../lib/state";
import BoxOverlay, { type BoxInteraction } from "./BoxOverlay";
import DropArea from "./DropArea";
import type { Sample } from "./SamplePicker";

interface Props {
  image: ImagePreview | null;
  boxes: Box[];
  loading: boolean;
  zoom: Zoom;
  selection: Selection | null;
  interaction: BoxInteraction;
  onZoom: () => void;
  onChoose: () => void;
  onFile: (file: File) => void;
  onSample: (sample: Sample) => void;
  onImageLoaded: (image: ImagePreview) => void;
  onImageFailed: (url: string) => void;
}

export default function DocumentViewer(props: Props) {
  const viewer = useRef<HTMLDivElement>(null);
  const { selection } = props;
  useEffect(() => {
    if (selection?.source !== "row") return;
    const rectangle = viewer.current?.querySelector(`[data-box-index="${selection.index}"]`);
    rectangle?.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  }, [selection]);

  const image = props.image;
  return (
    <section
      className="viewer-region"
      aria-label="Document viewer"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file) props.onFile(file);
      }}
    >
      {image && (
        <div className="viewer-tools">
          <button
            type="button"
            onClick={props.onZoom}
            aria-label={`Zoom: ${props.zoom === "fit" ? "Fit" : "100%"}. Toggle zoom`}
          >
            {props.zoom === "fit" ? "Fit" : "100%"}
          </button>
        </div>
      )}
      {props.loading && <progress aria-label="Detecting" />}
      <div className="viewer-scroll" ref={viewer}>
        {image ? (
          <div
            className={`document-sheet ${props.zoom}`}
            style={props.zoom === "actual" && image.width ? { width: image.width } : undefined}
          >
            <img
              src={image.url}
              alt={image.name}
              onLoad={(event) =>
                props.onImageLoaded({
                  ...image,
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
              onError={() => props.onImageFailed(image.url)}
            />
            {image.width > 0 && image.height > 0 && (
              <BoxOverlay
                boxes={props.boxes}
                width={image.width}
                height={image.height}
                interaction={props.interaction}
              />
            )}
          </div>
        ) : (
          <DropArea onChoose={props.onChoose} onSample={props.onSample} />
        )}
      </div>
    </section>
  );
}
