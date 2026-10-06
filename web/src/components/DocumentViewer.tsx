import { useEffect, useRef, useState } from "react";

import type { Box } from "../lib/api";
import type { ImagePreview, Selection, Zoom } from "../lib/state";
import BoxOverlay, { type BoxInteraction } from "./BoxOverlay";
import DropArea from "./DropArea";
import CoordinateTag from "./CoordinateTag";
import SamplePicker, { type Sample } from "./SamplePicker";
import Footer from "./Footer";

interface Props {
  idle: boolean;
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
  const [dragging, setDragging] = useState(false);
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
      className={`viewer-region${dragging ? " dragging" : ""}`}
      aria-label="Document viewer"
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        const file = event.dataTransfer.files[0];
        if (file) props.onFile(file);
      }}
    >
      {!props.idle && (
        <div className="viewer-samples">
          <SamplePicker onChoose={props.onSample} />
        </div>
      )}
      {image && (
        <div className="viewer-tools">
          <p className="viewer-caption">
            {image.name}
            {image.width > 0 && ` · ${image.width} × ${image.height}`}
          </p>
          <button
            type="button"
            className={`zoom-control ${props.zoom}`}
            onClick={props.onZoom}
            aria-label={`Zoom: ${props.zoom === "fit" ? "Fit" : "100%"}. Toggle zoom`}
          >
            <span aria-hidden="true" className="zoom-fit">
              Fit
            </span>
            <span aria-hidden="true" className="zoom-actual">
              100%
            </span>
          </button>
        </div>
      )}
      <div className="viewer-scroll" ref={viewer}>
        {image ? (
          <div
            className={`document-sheet ${props.zoom}`}
            style={props.zoom === "actual" && image.width ? { width: image.width } : undefined}
          >
            {props.loading && (
              <div className="loading-bar" role="progressbar" aria-label="Detecting" />
            )}
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
            {image.width > 0 &&
              props.interaction.selected !== null &&
              props.boxes[props.interaction.selected] && (
                <CoordinateTag
                  box={props.boxes[props.interaction.selected]}
                  index={props.interaction.selected}
                />
              )}
          </div>
        ) : (
          <DropArea onChoose={props.onChoose} onSample={props.onSample} />
        )}
      </div>
      {props.idle && <Footer />}
    </section>
  );
}
