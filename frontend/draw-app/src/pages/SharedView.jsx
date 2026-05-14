import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";
import { drawingsAPI, checkAuth } from "../api";
import { localDrawings } from "../storage";

const barStyle = {
  height: 44,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 1rem",
  background: "#0b1121",
  borderBottom: "1px solid #1a2744",
  flexShrink: 0,
};

const btnStyle = {
  padding: "5px 14px",
  fontSize: "0.8rem",
  fontWeight: 600,
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  transition: "background 0.15s",
};

export default function SharedView({ theme }) {
  const { shareId } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(undefined);
  const [drawing, setDrawing] = useState(null);
  const [error, setError] = useState(null);
  const [forking, setForking] = useState(false);

  useEffect(() => {
    checkAuth().then((u) => setUser(u || null));
  }, []);

  useEffect(() => {
    if (!shareId) return;
    drawingsAPI
      .getShared(shareId)
      .then(setDrawing)
      .catch(() => setError("Drawing not found or link is invalid."));
  }, [shareId]);

  const handleFork = useCallback(async () => {
    if (!drawing) return;
    setForking(true);

    try {
      if (user) {
        const result = await drawingsAPI.create({
          title: `${drawing.title} (copy)`,
          data: drawing.data,
        });
        navigate(`/edit/${result.share_id}`);
      } else {
        const result = localDrawings.create({
          title: `${drawing.title} (copy)`,
          data: drawing.data,
        });
        navigate(`/local/${result.id}`);
      }
    } catch (err) {
      console.error("Fork failed:", err);
      setForking(false);
    }
  }, [drawing, user, navigate]);

  if (error) {
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
        <p style={{ fontSize: "1.1rem" }}>{error}</p>
        <button
          style={{ ...btnStyle, background: "#374151", color: "#e5e7eb" }}
          onClick={() => navigate("/")}
        >
          Back to Gallery
        </button>
      </div>
    );
  }

  if (!drawing) {
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
        Loading shared drawing...
      </div>
    );
  }

  return (
    <div style={{ height: "calc(100vh - 56px)", display: "flex", flexDirection: "column" }}>
      <div style={barStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 500,
              color: "#818cf8",
              background: "rgba(129,140,248,0.1)",
              padding: "3px 10px",
              borderRadius: 12,
            }}
          >
            Shared
          </span>
          <span style={{ fontSize: "0.95rem", fontWeight: 600, color: "#e5e7eb" }}>
            {drawing.title}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            style={{ ...btnStyle, background: "#374151", color: "#e5e7eb" }}
            onClick={() => navigate("/")}
          >
            Gallery
          </button>
          <button
            style={{ ...btnStyle, background: "#4f46e5", color: "#fff" }}
            onClick={handleFork}
            disabled={forking}
            onMouseEnter={(e) => (e.target.style.background = "#4338ca")}
            onMouseLeave={(e) => (e.target.style.background = "#4f46e5")}
          >
            {forking ? "Forking..." : "Fork & Edit"}
          </button>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        <Excalidraw
          theme={theme}
          initialData={drawing.data}
          viewModeEnabled={true}
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
