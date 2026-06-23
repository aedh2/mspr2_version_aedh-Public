"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Camera } from "lucide-react";
import { ChartCard } from "@/src/components/ui/cards";
import { Modal } from "@/src/components/ui/modal";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { formatDate } from "@/src/lib/format";
import type { ProgressionPhoto } from "@/src/types/domain";
import { Page } from "./_shared";

type PhotoPair = {
  key: string;
  before?: ProgressionPhoto;
  after?: ProgressionPhoto;
};

export function PhotosPage() {
  const [selected, setSelected] = useState<ProgressionPhoto | null>(null);
  const query = usePagedApi<ProgressionPhoto>("/api/me/photos", {}, 12);
  const photos = query.data?.data || [];

  const pairs = useMemo<PhotoPair[]>(() => {
    const keyed = new Map<string, PhotoPair>();
    const withoutGoal: ProgressionPhoto[] = [];

    photos.forEach((photo) => {
      if (photo.objectif_id) {
        const key = `objectif-${photo.objectif_id}`;
        const entry = keyed.get(key) || { key };
        const kind = (photo.type_photo || "").toUpperCase();
        if ((kind.includes("BEFORE") || kind.includes("AVANT")) && !entry.before) entry.before = photo;
        else if ((kind.includes("AFTER") || kind.includes("APRES")) && !entry.after) entry.after = photo;
        else if (!entry.before) entry.before = photo;
        else if (!entry.after) entry.after = photo;
        keyed.set(key, entry);
      } else {
        withoutGoal.push(photo);
      }
    });

    const befores = withoutGoal
      .filter((photo) => {
        const kind = (photo.type_photo || "").toUpperCase();
        return kind.includes("BEFORE") || kind.includes("AVANT");
      })
      .sort((left, right) => String(left.prise_le || "").localeCompare(String(right.prise_le || "")));
    const afters = withoutGoal
      .filter((photo) => {
        const kind = (photo.type_photo || "").toUpperCase();
        return kind.includes("AFTER") || kind.includes("APRES");
      })
      .sort((left, right) => String(left.prise_le || "").localeCompare(String(right.prise_le || "")));
    const leftovers = withoutGoal.filter((photo) => {
      const kind = (photo.type_photo || "").toUpperCase();
      return !kind.includes("BEFORE") && !kind.includes("AVANT") && !kind.includes("AFTER") && !kind.includes("APRES");
    });

    const loosePairs: PhotoPair[] = [];
    const maxPairs = Math.max(befores.length, afters.length);
    for (let index = 0; index < maxPairs; index += 1) {
      loosePairs.push({
        key: `loose-${index}`,
        before: befores[index],
        after: afters[index]
      });
    }
    leftovers.forEach((photo, index) => {
      loosePairs.push({ key: `leftover-${index}`, before: photo });
    });

    return [...Array.from(keyed.values()), ...loosePairs];
  }, [photos]);

  return (
    <Page title="Photos de progression" eyebrow="Suivi visuel">
      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <ChartCard title="Comparaisons avant / apres">
            {pairs.length === 0 ? (
              <div className="muted">Aucune photo enregistree.</div>
            ) : (
              <div className="photo-comparison-list">
                {pairs.map((pair) => (
                  <article key={pair.key} className="photo-comparison-card">
                    <PhotoColumn photo={pair.before} label="BEFORE" onOpen={setSelected} />
                    <div className="photo-arrow">
                      <ArrowRight size={22} />
                    </div>
                    <PhotoColumn photo={pair.after} label="AFTER" onOpen={setSelected} />
                  </article>
                ))}
              </div>
            )}
          </ChartCard>

          <ChartCard title="Galerie">
            {photos.length === 0 ? (
              <div className="muted">Aucune photo enregistree.</div>
            ) : (
              <div className="gallery-grid gallery-grid-compact">
                {photos.map((photo) => (
                  <button key={photo.photo_id} type="button" className="gallery-card-button" onClick={() => setSelected(photo)}>
                    {photo.photo_url || photo.image_url || photo.url || photo.image_path ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={photo.photo_url || photo.image_url || photo.url || photo.image_path || ""} alt={photo.commentaire || `Photo ${photo.photo_id}`} loading="lazy" />
                    ) : (
                      <div className="exercise-thumb-fallback"><Camera size={20} /></div>
                    )}
                    <div className="gallery-caption">
                      <strong>{photo.type_photo || "Photo"}</strong>
                      <span>{formatDate(photo.prise_le)}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </ChartCard>
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}

      <Modal title={selected?.type_photo || "Apercu photo"} open={Boolean(selected)} onClose={() => setSelected(null)} className="image-modal">
        {selected ? (
          <div className="image-preview-stack">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={selected.photo_url || selected.image_url || selected.url || selected.image_path || ""} alt={selected.commentaire || "Photo de progression"} className="image-preview" />
            <div className="muted">
              {formatDate(selected.prise_le)} {selected.commentaire ? `· ${selected.commentaire}` : ""}
            </div>
          </div>
        ) : null}
      </Modal>
    </Page>
  );
}

function PhotoColumn({
  photo,
  label,
  onOpen
}: {
  photo?: ProgressionPhoto;
  label: string;
  onOpen: (photo: ProgressionPhoto) => void;
}) {
  if (!photo) {
    return (
      <div className="photo-column photo-column-empty">
        <span className="photo-label">{label}</span>
        <div className="exercise-thumb-fallback"><Camera size={20} /></div>
        <p className="muted">Photo indisponible.</p>
      </div>
    );
  }

  return (
    <button type="button" className="photo-column" onClick={() => onOpen(photo)}>
      <span className="photo-label">{label}</span>
      {photo.photo_url || photo.image_url || photo.url || photo.image_path ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photo.photo_url || photo.image_url || photo.url || photo.image_path || ""} alt={`${label} ${photo.commentaire || ""}`} loading="lazy" />
      ) : (
        <div className="exercise-thumb-fallback"><Camera size={20} /></div>
      )}
      <div className="photo-meta">
        <strong>{formatDate(photo.prise_le)}</strong>
        {photo.commentaire ? <span>{photo.commentaire}</span> : null}
        {photo.objectif_id ? <span>Objectif #{photo.objectif_id}</span> : null}
      </div>
    </button>
  );
}
