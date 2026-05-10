import React, { useState, useCallback } from "react";
import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";

export default function App() {
  const [theme, setTheme] = useState("dark");

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.body.style.background = next === "dark" ? "#070f20" : "#ffffff";
    document.querySelector(".navbar").dataset.theme = next;
  }, [theme]);

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <button
        onClick={toggle}
        title="Toggle theme"
        style={{
          position: "fixed",
          top: 14,
          right: 24,
          zIndex: 200,
          background: theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)",
          border: "1px solid " + (theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.12)"),
          borderRadius: 8,
          padding: "6px 8px",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.2s",
        }}
      >
        {theme === "dark" ? (
          <svg width="18" height="18" fill="none" stroke="#fbbf24" strokeWidth="2" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
        ) : (
          <svg width="18" height="18" fill="none" stroke="#4f46e5" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
          </svg>
        )}
      </button>
      <Excalidraw
        theme={theme}
        UIOptions={{
          canvasActions: {
            loadScene: false,
            saveToActiveFile: false,
          },
        }}
      />
    </div>
  );
}
