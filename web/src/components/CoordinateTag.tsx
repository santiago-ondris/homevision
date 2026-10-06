import { useEffect, useRef, useState } from "react";

import type { Box } from "../lib/api";

interface Props {
  box: Box;
  index: number;
}

export default function CoordinateTag({ box, index }: Props) {
  const tag = useRef<HTMLSpanElement>(null);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);

  useEffect(() => {
    const label = tag.current;
    const sheet = label?.parentElement;
    const viewer = sheet?.parentElement;
    const rectangle = sheet?.querySelector(`[data-box-index="${index}"]`);
    if (!label || !sheet || !viewer || !rectangle) return;

    function placeTag() {
      if (!label || !sheet || !viewer || !rectangle) return;
      const bounds = rectangle.getBoundingClientRect();
      const origin = sheet.getBoundingClientRect();
      const above = bounds.top - label.offsetHeight;
      const top = above >= viewer.getBoundingClientRect().top ? above : bounds.bottom;
      setPosition({
        left: bounds.left - origin.left - sheet.clientLeft,
        top: top - origin.top - sheet.clientTop,
      });
    }

    const observer = new ResizeObserver(placeTag);
    observer.observe(sheet);
    observer.observe(label);
    viewer.addEventListener("scroll", placeTag);
    placeTag();
    return () => {
      observer.disconnect();
      viewer.removeEventListener("scroll", placeTag);
    };
  }, [box, index]);

  return (
    <span
      ref={tag}
      className="coordinate-tag"
      aria-hidden="true"
      style={position ?? { visibility: "hidden" }}
    >
      [{box.bbox.join(", ")}]
    </span>
  );
}
