import React, { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Routes, Route } from "react-router-dom";
import Gallery from "./pages/Gallery";
import Editor from "./pages/Editor";
import SharedView from "./pages/SharedView";
import AuthButton from "./components/AuthButton";
import { checkAuth } from "./api";

const sunIcon = (
  <svg width="16" height="16" fill="none" stroke="#fbbf24" strokeWidth="2" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="5" />
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
  </svg>
);

const moonIcon = (
  <svg width="16" height="16" fill="none" stroke="#4f46e5" strokeWidth="2" viewBox="0 0 24 24">
    <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
  </svg>
);

export default function App() {
  const [theme, setTheme] = useState("dark");
  const [user, setUser] = useState(undefined); // undefined=loading, null=anon, object=logged in

  useEffect(() => {
    checkAuth().then((u) => setUser(u || null));
  }, []);

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.body.style.background = next === "dark" ? "#070f20" : "#ffffff";
    const navbar = document.querySelector(".navbar");
    if (navbar) navbar.dataset.theme = next;
  }, [theme]);

  const toggleSlot = document.getElementById("theme-toggle-slot");

  return (
    <>
      {/* Auth controls in navbar */}
      {user !== undefined && (
        <AuthButton user={user} onAuthChange={setUser} />
      )}

      {/* Theme toggle in navbar */}
      {toggleSlot &&
        createPortal(
          <button
            onClick={toggle}
            title="Toggle theme"
            style={{
              background:
                theme === "dark"
                  ? "rgba(255,255,255,0.1)"
                  : "rgba(0,0,0,0.08)",
              border:
                "1px solid " +
                (theme === "dark"
                  ? "rgba(255,255,255,0.15)"
                  : "rgba(0,0,0,0.12)"),
              borderRadius: 8,
              padding: "5px 7px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s",
            }}
          >
            {theme === "dark" ? sunIcon : moonIcon}
          </button>,
          toggleSlot
        )}

      <Routes>
        <Route path="/" element={<Gallery user={user} />} />
        <Route path="/new" element={<Editor theme={theme} user={user} />} />
        <Route path="/edit/:shareId" element={<Editor theme={theme} user={user} />} />
        <Route path="/local/:localId" element={<Editor theme={theme} user={user} />} />
        <Route path="/s/:shareId" element={<SharedView theme={theme} user={user} />} />
      </Routes>
    </>
  );
}
