import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { drawingsAPI } from "../api";
import { localDrawings } from "../storage";

function timeAgo(iso) {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

const S = {
  wrapper: {
    height: "calc(100vh - 56px)",
    overflowY: "auto",
    background: "#070f20",
    padding: "2rem",
  },
  container: { maxWidth: 1100, margin: "0 auto" },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "1.5rem",
  },
  title: { fontSize: "1.5rem", fontWeight: 700, color: "#f3f4f6" },
  newBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "0.6rem 1.2rem",
    background: "#4f46e5",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontSize: "0.875rem",
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 0.15s",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
    gap: "1.25rem",
  },
  card: {
    background: "#0f1729",
    border: "1px solid #1a3464",
    borderRadius: 14,
    overflow: "hidden",
    cursor: "pointer",
    transition: "border-color 0.2s, transform 0.15s, box-shadow 0.2s",
    display: "flex",
    flexDirection: "column",
  },
  thumbWrap: {
    position: "relative",
    width: "100%",
    height: 200,
    background: "#111827",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  thumb: {
    maxWidth: "100%",
    maxHeight: "100%",
    objectFit: "contain",
    padding: 12,
    display: "block",
  },
  zoomHint: {
    position: "absolute",
    inset: 0,
    display: "none",
    alignItems: "center",
    justifyContent: "center",
    background: "rgba(0,0,0,0.35)",
    transition: "opacity 0.15s",
  },
  zoomBadge: {
    background: "rgba(0,0,0,0.7)",
    color: "#fff",
    fontSize: "0.7rem",
    fontWeight: 500,
    padding: "4px 10px",
    borderRadius: 6,
  },
  thumbPlaceholder: {
    width: "100%",
    height: 200,
    background: "#111827",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#374151",
  },
  cardBody: {
    padding: "1rem 1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    flex: 1,
    borderTop: "1px solid #1a2744",
  },
  cardTitle: {
    fontSize: "0.95rem",
    fontWeight: 600,
    color: "#e5e7eb",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  cardMeta: { fontSize: "0.75rem", color: "#6b7280" },
  cardActions: { display: "flex", gap: 8, marginTop: "auto" },
  smallBtn: {
    padding: "4px 10px",
    fontSize: "0.75rem",
    fontWeight: 500,
    border: "1px solid #374151",
    borderRadius: 6,
    cursor: "pointer",
    background: "transparent",
    color: "#9ca3af",
    transition: "all 0.15s",
  },
  deleteBtn: {
    padding: "4px 10px",
    fontSize: "0.75rem",
    fontWeight: 500,
    border: "1px solid #7f1d1d",
    borderRadius: 6,
    cursor: "pointer",
    background: "transparent",
    color: "#f87171",
    transition: "all 0.15s",
  },
  sectionLabel: {
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "#6b7280",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "0.75rem",
    marginTop: "2rem",
  },
  empty: {
    textAlign: "center",
    padding: "4rem 1rem",
    color: "#6b7280",
  },
  migrateBanner: {
    background: "#1e1b4b",
    border: "1px solid #3730a3",
    borderRadius: 10,
    padding: "0.85rem 1.25rem",
    marginBottom: "1rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontSize: "0.85rem",
    color: "#c7d2fe",
  },
  migrateBtn: {
    padding: "6px 14px",
    fontSize: "0.8rem",
    fontWeight: 600,
    background: "#4f46e5",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
  },
  // Lightbox
  lightbox: {
    position: "fixed",
    inset: 0,
    zIndex: 200,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "rgba(0,0,0,0.85)",
    padding: "2rem",
    cursor: "zoom-out",
  },
  lightboxInner: {
    position: "relative",
    maxWidth: "90vw",
    maxHeight: "85vh",
    cursor: "default",
  },
  lightboxImg: {
    maxWidth: "90vw",
    maxHeight: "80vh",
    objectFit: "contain",
    borderRadius: 12,
    background: "#fff",
    padding: 16,
  },
  lightboxCaption: {
    textAlign: "center",
    marginTop: 12,
    fontSize: "0.85rem",
    color: "#d1d5db",
    fontWeight: 500,
  },
  lightboxClose: {
    position: "absolute",
    top: -36,
    right: 0,
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.7)",
    fontSize: "0.85rem",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
};

const placeholderIcon = (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="1.5">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M8 12h8M12 8v8" />
  </svg>
);

function DrawingCard({ drawing, isLocal, onDelete, onShare, copiedId, onPreview }) {
  const navigate = useNavigate();
  const thumb = drawing.thumbnail;

  return (
    <div
      style={S.card}
      onClick={() =>
        navigate(isLocal ? `/local/${drawing.id}` : `/edit/${drawing.share_id}`)
      }
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#3b82f6";
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 24px rgba(59,130,246,0.15)";
        const hint = e.currentTarget.querySelector("[data-zoom-hint]");
        if (hint) hint.style.display = "flex";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#1a3464";
        e.currentTarget.style.transform = "none";
        e.currentTarget.style.boxShadow = "none";
        const hint = e.currentTarget.querySelector("[data-zoom-hint]");
        if (hint) hint.style.display = "none";
      }}
    >
      {thumb ? (
        <div style={S.thumbWrap}>
          <img src={thumb} alt="" style={S.thumb} />
          <div
            data-zoom-hint
            style={S.zoomHint}
            onClick={(e) => {
              e.stopPropagation();
              onPreview(thumb, drawing.title);
            }}
          >
            <span style={S.zoomBadge}>Click to zoom</span>
          </div>
        </div>
      ) : (
        <div style={S.thumbPlaceholder}>{placeholderIcon}</div>
      )}
      <div style={S.cardBody}>
        <div style={S.cardTitle}>{drawing.title}</div>
        <div style={S.cardMeta}>
          Updated {timeAgo(drawing.updated_at)}
        </div>
        <div style={S.cardActions}>
          {!isLocal && onShare && (
            <button
              style={S.smallBtn}
              onClick={(e) => {
                e.stopPropagation();
                onShare(drawing.share_id);
              }}
            >
              {copiedId === drawing.share_id ? "Copied!" : "Share"}
            </button>
          )}
          <button
            style={S.deleteBtn}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(drawing, isLocal);
            }}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

function Lightbox({ src, caption, onClose }) {
  if (!src) return null;
  return (
    <div style={S.lightbox} onClick={onClose}>
      <div style={S.lightboxInner} onClick={(e) => e.stopPropagation()}>
        <button style={S.lightboxClose} onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
          Close
        </button>
        <img src={src} alt={caption} style={S.lightboxImg} />
        {caption && <div style={S.lightboxCaption}>{caption}</div>}
      </div>
    </div>
  );
}

export default function Gallery({ user }) {
  const navigate = useNavigate();
  const [cloudDrawings, setCloudDrawings] = useState([]);
  const [localList, setLocalList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState(null);
  const [migrating, setMigrating] = useState(false);
  const [lightbox, setLightbox] = useState({ src: null, caption: null });

  useEffect(() => {
    if (user === undefined) return;
    let cancelled = false;

    (async () => {
      if (user) {
        try {
          const res = await drawingsAPI.list();
          if (!cancelled) setCloudDrawings(res.items);
        } catch (err) {
          console.error("Failed to load drawings:", err);
        }
      }
      if (!cancelled) {
        setLocalList(localDrawings.list());
        setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [user]);

  const handleDelete = useCallback(async (drawing, isLocal) => {
    if (!confirm(`Delete "${drawing.title}"?`)) return;
    if (isLocal) {
      localDrawings.delete(drawing.id);
      setLocalList(localDrawings.list());
    } else {
      await drawingsAPI.delete(drawing.id);
      setCloudDrawings((prev) => prev.filter((d) => d.id !== drawing.id));
    }
  }, []);

  const handleShare = useCallback((shareId) => {
    const url = `${window.location.origin}/draw/s/${shareId}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopiedId(shareId);
      setTimeout(() => setCopiedId(null), 2000);
    });
  }, []);

  const handlePreview = useCallback((src, caption) => {
    setLightbox({ src, caption });
  }, []);

  const closeLightbox = useCallback(() => {
    setLightbox({ src: null, caption: null });
  }, []);

  // Close lightbox on Escape
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") closeLightbox();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [closeLightbox]);

  const handleMigrateAll = useCallback(async () => {
    setMigrating(true);
    for (const d of localDrawings.list()) {
      try {
        await drawingsAPI.create({ title: d.title, data: d.data, thumbnail: d.thumbnail });
      } catch (err) {
        console.error("Migration failed for:", d.title, err);
      }
    }
    localDrawings.clear();
    setLocalList([]);
    const res = await drawingsAPI.list();
    setCloudDrawings(res.items);
    setMigrating(false);
  }, []);

  if (loading || user === undefined) {
    return (
      <div style={{ ...S.wrapper, display: "flex", alignItems: "center", justifyContent: "center", color: "#6b7280" }}>
        Loading drawings...
      </div>
    );
  }

  const hasCloud = cloudDrawings.length > 0;
  const hasLocal = localList.length > 0;
  const isEmpty = !hasCloud && !hasLocal;

  return (
    <div style={S.wrapper}>
      <div style={S.container}>
        <div style={S.header}>
          <h1 style={S.title}>My Drawings</h1>
          <button
            style={S.newBtn}
            onClick={() => navigate("/new")}
            onMouseEnter={(e) => (e.target.style.background = "#4338ca")}
            onMouseLeave={(e) => (e.target.style.background = "#4f46e5")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Drawing
          </button>
        </div>

        {isEmpty && (
          <div style={S.empty}>
            <div style={{ marginBottom: "1rem", opacity: 0.4 }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#4b5563" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M8 12h8M12 8v8" />
              </svg>
            </div>
            <p style={{ fontSize: "1.1rem", color: "#9ca3af", marginBottom: 8 }}>
              No drawings yet
            </p>
            <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>
              Create your first freehand drawing to get started.
            </p>
          </div>
        )}

        {/* Cloud drawings */}
        {user && hasCloud && (
          <>
            <div style={S.sectionLabel}>Cloud Drawings</div>
            <div style={S.grid}>
              {cloudDrawings.map((d) => (
                <DrawingCard
                  key={d.id}
                  drawing={d}
                  isLocal={false}
                  onDelete={handleDelete}
                  onShare={handleShare}
                  onPreview={handlePreview}
                  copiedId={copiedId}
                />
              ))}
            </div>
          </>
        )}

        {/* Migration banner */}
        {user && hasLocal && (
          <>
            <div style={S.sectionLabel}>Local Drawings</div>
            <div style={S.migrateBanner}>
              <span>
                {localList.length} drawing{localList.length > 1 ? "s" : ""} saved
                locally. Save to cloud for sharing and cross-device access.
              </span>
              <button style={S.migrateBtn} onClick={handleMigrateAll} disabled={migrating}>
                {migrating ? "Migrating..." : "Save All to Cloud"}
              </button>
            </div>
          </>
        )}

        {/* Local drawings */}
        {hasLocal && (
          <>
            {!user && <div style={S.sectionLabel}>Saved Locally</div>}
            {!user && (
              <p style={{ fontSize: "0.8rem", color: "#6b7280", marginBottom: "1rem", marginTop: "-0.5rem" }}>
                Sign in to save drawings to the cloud and share them.
              </p>
            )}
            <div style={S.grid}>
              {localList.map((d) => (
                <DrawingCard
                  key={d.id}
                  drawing={d}
                  isLocal={true}
                  onDelete={handleDelete}
                  onPreview={handlePreview}
                  copiedId={copiedId}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Lightbox */}
      <Lightbox src={lightbox.src} caption={lightbox.caption} onClose={closeLightbox} />
    </div>
  );
}
