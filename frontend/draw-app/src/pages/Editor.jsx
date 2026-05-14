import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";
import { drawingsAPI, checkAuth } from "../api";
import { localDrawings } from "../storage";

const AUTOSAVE_DELAY = 3000;

const toolbarStyle = {
  height: 44,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 1rem",
  background: "#0b1121",
  borderBottom: "1px solid #1a2744",
  flexShrink: 0,
};

const backBtn = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  background: "none",
  border: "none",
  color: "#9ca3af",
  cursor: "pointer",
  fontSize: "0.8rem",
  fontWeight: 500,
  padding: "4px 8px",
  borderRadius: 6,
  transition: "color 0.15s",
};

const titleInput = {
  background: "transparent",
  border: "1px solid transparent",
  color: "#e5e7eb",
  fontSize: "0.95rem",
  fontWeight: 600,
  padding: "4px 8px",
  borderRadius: 6,
  outline: "none",
  maxWidth: 300,
  transition: "border-color 0.15s",
  fontFamily: "Inter, system-ui, sans-serif",
};

const statusStyle = {
  fontSize: "0.75rem",
  fontWeight: 500,
  padding: "3px 10px",
  borderRadius: 12,
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
};

const shareBtn = {
  padding: "5px 12px",
  fontSize: "0.8rem",
  fontWeight: 600,
  background: "#4f46e5",
  color: "#fff",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  transition: "background 0.15s",
};

function SaveStatus({ status }) {
  const config = {
    saved: { color: "#34d399", bg: "rgba(52,211,153,0.1)", label: "Saved", dot: true },
    saving: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", label: "Saving...", dot: true },
    unsaved: { color: "#6b7280", bg: "rgba(107,114,128,0.1)", label: "Unsaved", dot: false },
  }[status];

  return (
    <span style={{ ...statusStyle, color: config.color, background: config.bg }}>
      {config.dot && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: config.color,
          }}
        />
      )}
      {config.label}
    </span>
  );
}

export default function Editor({ theme }) {
  const { shareId, localId } = useParams();
  const navigate = useNavigate();

  const [user, setUser] = useState(undefined);
  const [title, setTitle] = useState("Untitled");
  const [initialData, setInitialData] = useState(null);
  const [drawingMeta, setDrawingMeta] = useState(null); // { id, share_id }
  const [currentLocalId, setCurrentLocalId] = useState(localId || null);
  const [saveStatus, setSaveStatus] = useState("saved");
  const [copied, setCopied] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const sceneRef = useRef({ elements: [], files: {} });
  const saveTimerRef = useRef(null);
  const isNew = !shareId && !localId;

  // Check auth
  useEffect(() => {
    checkAuth().then((u) => setUser(u || null));
  }, []);

  // Load drawing data
  useEffect(() => {
    if (user === undefined) return;

    if (isNew) {
      setInitialData({ elements: [], appState: {}, files: {} });
      setSaveStatus("unsaved");
      return;
    }

    if (localId) {
      const d = localDrawings.get(localId);
      if (d) {
        setTitle(d.title);
        setCurrentLocalId(d.id);
        setInitialData(d.data || { elements: [], appState: {}, files: {} });
      } else {
        setLoadError("Drawing not found");
      }
      return;
    }

    if (shareId) {
      // Load via shared endpoint (works for owner too)
      drawingsAPI
        .getShared(shareId)
        .then((d) => {
          setTitle(d.title);
          setDrawingMeta({ id: d.id, share_id: d.share_id });
          setInitialData(d.data || { elements: [], appState: {}, files: {} });
        })
        .catch(() => setLoadError("Drawing not found"));
    }
  }, [user, shareId, localId, isNew]);

  const doSave = useCallback(async () => {
    const { elements, files } = sceneRef.current;
    if (!elements.length && isNew) return; // don't save empty new drawings

    const data = { elements, files: files || {} };
    setSaveStatus("saving");

    try {
      if (user) {
        if (drawingMeta) {
          await drawingsAPI.update(drawingMeta.id, { title, data });
        } else {
          const result = await drawingsAPI.create({ title, data });
          setDrawingMeta({ id: result.id, share_id: result.share_id });
          window.history.replaceState(null, "", `/draw/edit/${result.share_id}`);
        }
      } else {
        if (currentLocalId) {
          localDrawings.update(currentLocalId, { title, data });
        } else {
          const result = localDrawings.create({ title, data });
          setCurrentLocalId(result.id);
          window.history.replaceState(null, "", `/draw/local/${result.id}`);
        }
      }
      setSaveStatus("saved");
    } catch (err) {
      console.error("Save failed:", err);
      setSaveStatus("unsaved");
    }
  }, [user, drawingMeta, currentLocalId, title, isNew]);

  // Save title changes
  const handleTitleBlur = useCallback(() => {
    if (drawingMeta || currentLocalId) {
      doSave();
    }
  }, [doSave, drawingMeta, currentLocalId]);

  const onChange = useCallback(
    (elements, appState, files) => {
      sceneRef.current = { elements: [...elements], files: { ...files } };

      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      setSaveStatus("unsaved");
      saveTimerRef.current = setTimeout(() => doSave(), AUTOSAVE_DELAY);
    },
    [doSave]
  );

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const handleShare = useCallback(() => {
    if (!drawingMeta?.share_id) return;
    const url = `${window.location.origin}/draw/s/${drawingMeta.share_id}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [drawingMeta]);

  if (loadError) {
    return (
      <div
        style={{
          height: "calc(100vh - 56px)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#070f20",
          color: "#9ca3af",
          gap: 16,
        }}
      >
        <p style={{ fontSize: "1.1rem" }}>{loadError}</p>
        <button
          style={{ ...shareBtn, background: "#374151" }}
          onClick={() => navigate("/")}
        >
          Back to Gallery
        </button>
      </div>
    );
  }

  if (!initialData) {
    return (
      <div
        style={{
          height: "calc(100vh - 56px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#070f20",
          color: "#6b7280",
        }}
      >
        Loading...
      </div>
    );
  }

  return (
    <div style={{ height: "calc(100vh - 56px)", display: "flex", flexDirection: "column" }}>
      {/* Toolbar */}
      <div style={toolbarStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            style={backBtn}
            onClick={() => navigate("/")}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#e5e7eb")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#9ca3af")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Gallery
          </button>
          <div style={{ width: 1, height: 20, background: "#1a2744" }} />
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={(e) => e.key === "Enter" && e.target.blur()}
            style={titleInput}
            onFocus={(e) => (e.target.style.borderColor = "#3b82f6")}
            onBlurCapture={(e) => (e.target.style.borderColor = "transparent")}
            placeholder="Untitled"
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <SaveStatus status={saveStatus} />
          {user && drawingMeta?.share_id && (
            <button
              style={shareBtn}
              onClick={handleShare}
              onMouseEnter={(e) => (e.target.style.background = "#4338ca")}
              onMouseLeave={(e) => (e.target.style.background = "#4f46e5")}
            >
              {copied ? "Link Copied!" : "Share"}
            </button>
          )}
        </div>
      </div>

      {/* Excalidraw canvas */}
      <div style={{ flex: 1 }}>
        <Excalidraw
          theme={theme}
          initialData={initialData}
          onChange={onChange}
          UIOptions={{
            canvasActions: {
              loadScene: false,
              saveToActiveFile: false,
            },
          }}
        />
      </div>
    </div>
  );
}
