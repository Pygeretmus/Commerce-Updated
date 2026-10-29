import { useState } from "react";
import type { ListingImage } from "../api/types";

export function Gallery({
  images,
  title,
}: {
  images: ListingImage[];
  title: string;
}) {
  const [selected, setSelected] = useState(0);
  if (images.length === 0) {
    return <div className="gallery-main photo-missing">No photographs</div>;
  }
  const current = images[Math.min(selected, images.length - 1)];
  return (
    <div className="gallery">
      <a
        className="gallery-main"
        href={current.url}
        target="_blank"
        rel="noreferrer"
        title="Open the full-size photograph"
      >
        <img
          src={current.url}
          alt={`${title}, photograph ${selected + 1} of ${images.length}`}
        />
      </a>
      {images.length > 1 && (
        <ul className="gallery-thumbs" aria-label="Photographs">
          {images.map((image, index) => (
            <li key={image.id}>
              <button
                className={index === selected ? "is-selected" : undefined}
                aria-label={`Show photograph ${index + 1} of ${images.length}`}
                aria-current={index === selected}
                onClick={() => setSelected(index)}
              >
                <img src={image.thumbnail ?? image.url} alt="" loading="lazy" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
