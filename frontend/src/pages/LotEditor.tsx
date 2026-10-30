import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { catalogApi, sellerApi, type ListingInput } from "../api/endpoints";
import type { ListingDetail, ListingImage } from "../api/types";
import { ConfirmButton } from "../components/ConfirmButton";
import { Field, FormErrors, Select, TextArea } from "../components/Field";
import { ErrorNote, Loading } from "../components/StateNote";
import { lotNumber } from "../format";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useFetch } from "../hooks/useFetch";

const DURATIONS = [1, 3, 5, 7, 14];
const MAX_PHOTOS = 8;

interface FormState {
  title: string;
  description: string;
  category: string;
  starting_price: string;
  reserve_price: string;
}

function toForm(lot?: ListingDetail): FormState {
  return {
    title: lot?.title ?? "",
    description: lot?.description ?? "",
    category: "",
    starting_price: lot?.starting_price ?? "",
    reserve_price: lot?.reserve_price ?? "",
  };
}

function Details({
  lot,
  onSaved,
}: {
  lot?: ListingDetail;
  onSaved: (lot: ListingDetail) => void;
}) {
  const categories = useFetch("categories", () => catalogApi.categories());
  const [form, setForm] = useState<FormState>(() => toForm(lot));
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const set =
    (key: keyof FormState) => (event: { target: { value: string } }) => {
      setForm((f) => ({ ...f, [key]: event.target.value }));
      setSaved(false);
    };

  // The API returns the category by name, the form needs its id
  const categoryId =
    form.category ||
    String(
      categories.data?.find((c) => c.slug === lot?.category.slug)?.id ?? "",
    );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const input: ListingInput = {
      title: form.title.trim(),
      description: form.description.trim(),
      category: Number(categoryId),
      starting_price: form.starting_price.trim(),
      reserve_price: form.reserve_price.trim() || null,
    };
    try {
      const result = lot
        ? await sellerApi.update(lot.id, input)
        : await sellerApi.create(input);
      setSaved(true);
      onSaved(result);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="form" onSubmit={submit}>
      <FormErrors messages={error?.general ?? []} />
      <Field
        label="Title"
        required
        minLength={3}
        maxLength={120}
        value={form.title}
        onChange={set("title")}
        error={error?.field("title")}
      />
      <TextArea
        label="Description"
        required
        rows={7}
        maxLength={5000}
        value={form.description}
        onChange={set("description")}
        error={error?.field("description")}
        hint="Condition, size, history, flaws. Buyers cannot change their minds, so be honest."
      />
      <Select
        label="Category"
        required
        value={categoryId}
        onChange={set("category")}
        error={error?.field("category")}
      >
        <option value="" disabled>
          Choose a category
        </option>
        {categories.data?.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </Select>
      <div className="field-row">
        <Field
          label="Starting bid, $"
          required
          inputMode="decimal"
          value={form.starting_price}
          onChange={set("starting_price")}
          error={error?.field("starting_price")}
          hint="The first bid can be this amount."
        />
        <Field
          label="Reserve price, $ (optional)"
          inputMode="decimal"
          value={form.reserve_price}
          onChange={set("reserve_price")}
          error={error?.field("reserve_price")}
          hint="A secret minimum. If bidding ends below it, the lot is not sold."
        />
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" disabled={busy || !categoryId}>
          {busy
            ? "Saving…"
            : lot
              ? "Save details"
              : "Create draft and add photos"}
        </button>
        {saved && lot && (
          <span className="muted small" role="status">
            Saved.
          </span>
        )}
      </div>
    </form>
  );
}

function Photos({
  lot,
  images,
  setImages,
}: {
  lot: ListingDetail;
  images: ListingImage[];
  setImages: (images: ListingImage[]) => void;
}) {
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setErrors([]);
    const problems: string[] = [];
    let current = images;
    for (const file of Array.from(files)) {
      if (current.length >= MAX_PHOTOS) {
        problems.push(
          `${file.name}: a lot can have at most ${MAX_PHOTOS} photographs.`,
        );
        continue;
      }
      try {
        const image = await sellerApi.uploadImage(lot.id, file);
        current = [...current, image];
        setImages(current);
      } catch (e) {
        problems.push(
          `${file.name}: ${e instanceof ApiError ? e.message : "upload failed"}`,
        );
      }
    }
    setErrors(problems);
    setBusy(false);
    if (input.current) input.current.value = "";
  };

  const remove = async (image: ListingImage) => {
    try {
      await sellerApi.removeImage(lot.id, image.id);
      setImages(images.filter((i) => i.id !== image.id));
    } catch (e) {
      setErrors([
        e instanceof ApiError ? e.message : "Could not remove the photograph.",
      ]);
    }
  };

  const move = async (index: number, delta: number) => {
    const next = [...images];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    setImages(next);
    try {
      await sellerApi.orderImages(
        lot.id,
        next.map((i) => i.id),
      );
    } catch (e) {
      setImages(images);
      setErrors([e instanceof ApiError ? e.message : "Could not reorder."]);
    }
  };

  return (
    <section className="section" aria-labelledby="photos-title">
      <h2 id="photos-title">Photographs</h2>
      <p className="muted small">
        Up to {MAX_PHOTOS} photographs (JPEG, PNG or WEBP, 5 MB each). The first
        one is the cover. Location data is removed from every file.
      </p>
      <FormErrors messages={errors} />
      {images.length > 0 && (
        <ul className="photo-list">
          {images.map((image, index) => (
            <li key={image.id}>
              <img
                src={image.thumbnail ?? image.url}
                alt={`Photograph ${index + 1}`}
              />
              <div className="photo-actions">
                {index === 0 && <span className="tag tag-lead">cover</span>}
                <button
                  className="btn btn-quiet small"
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                  aria-label={`Move photograph ${index + 1} earlier`}
                >
                  ←
                </button>
                <button
                  className="btn btn-quiet small"
                  disabled={index === images.length - 1}
                  onClick={() => move(index, 1)}
                  aria-label={`Move photograph ${index + 1} later`}
                >
                  →
                </button>
                <button
                  className="btn btn-danger-quiet small"
                  onClick={() => remove(image)}
                  aria-label={`Remove photograph ${index + 1}`}
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <label className={`dropzone${busy ? " is-busy" : ""}`}>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          disabled={busy || images.length >= MAX_PHOTOS}
          onChange={(e) => upload(e.target.files)}
        />
        <span>
          {busy
            ? "Uploading…"
            : images.length >= MAX_PHOTOS
              ? "Photograph limit reached"
              : "Choose photographs to upload"}
        </span>
      </label>
    </section>
  );
}

function Publish({
  lot,
  photoCount,
}: {
  lot: ListingDetail;
  photoCount: number;
}) {
  const navigate = useNavigate();
  const [days, setDays] = useState("7");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const publish = async () => {
    setBusy(true);
    setError(null);
    try {
      await sellerApi.publish(lot.id, Number(days));
      navigate(`/lots/${lot.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e : null);
      setBusy(false);
    }
  };

  return (
    <section className="section" aria-labelledby="publish-title">
      <h2 id="publish-title">Put it on the block</h2>
      <p className="muted small">
        After publishing, the lot can no longer be edited: bidders rely on what
        they read.
      </p>
      <FormErrors messages={error?.errors.map((e) => e.message) ?? []} />
      <div className="form-actions">
        <div className="field inline-field">
          <label htmlFor="days">Auction runs for</label>
          <select
            id="days"
            value={days}
            onChange={(e) => setDays(e.target.value)}
          >
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {d} {d === 1 ? "day" : "days"}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn btn-primary"
          onClick={publish}
          disabled={busy || photoCount === 0}
        >
          {busy ? "Publishing…" : "Publish lot"}
        </button>
      </div>
      {photoCount === 0 && (
        <p className="hint">Add at least one photograph first.</p>
      )}
    </section>
  );
}

export default function LotEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === undefined;
  useDocumentTitle(isNew ? "Sell a lot" : "Edit draft");

  const lot = useFetch(`edit:${id ?? "new"}`, (signal) =>
    isNew ? Promise.resolve(undefined) : catalogApi.get(id, signal),
  );
  const [images, setImages] = useState<ListingImage[] | null>(null);

  if (isNew) {
    return (
      <div className="narrow">
        <p className="eyebrow">Consign</p>
        <h1>Sell a lot</h1>
        <p className="muted">
          Describe the piece first; you will add photographs and choose the
          length of the auction on the next step.
        </p>
        <Details onSaved={(created) => navigate(`/lots/${created.id}/edit`)} />
      </div>
    );
  }

  if (lot.error) return <ErrorNote error={lot.error} onRetry={lot.reload} />;
  if (!lot.data) return <Loading />;
  const draft = lot.data;
  if (!draft.is_seller || draft.status !== "draft")
    return <Navigate to={`/lots/${draft.id}`} replace />;

  return (
    <div className="narrow">
      <p className="eyebrow">
        Draft · <span className="mono">{lotNumber(draft.id)}</span>
      </p>
      <h1>{draft.title}</h1>
      <Details lot={draft} onSaved={() => lot.reload()} />
      <Photos
        lot={draft}
        images={images ?? draft.images}
        setImages={setImages}
      />
      <Publish lot={draft} photoCount={(images ?? draft.images).length} />
      <section className="section danger-zone">
        <ConfirmButton
          confirmLabel="Yes, delete the draft"
          onConfirm={async () => {
            await sellerApi.remove(draft.id);
            navigate("/me/lots");
          }}
        >
          Delete this draft
        </ConfirmButton>
        <Link to="/me/lots" className="btn btn-quiet">
          Back to my lots
        </Link>
      </section>
    </div>
  );
}
