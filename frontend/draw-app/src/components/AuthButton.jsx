import React, { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

const googleIcon = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M21.8 10.2h-9.6v3.9h5.5c-.25 1.4-1.55 4.1-5.5 4.1-3.3 0-6-2.75-6-6.15s2.7-6.15 6-6.15c1.9 0 3.15.8 3.87 1.5l2.65-2.55C17.05 3.3 14.85 2.4 12.2 2.4 6.9 2.4 2.6 6.7 2.6 12s4.3 9.6 9.6 9.6c5.55 0 9.2-3.9 9.2-9.4 0-.63-.07-1.1-.15-1.55z" />
  </svg>
);

const githubIcon = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 007.86 10.93c.57.1.78-.25.78-.55 0-.27-.01-.98-.02-1.93-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.01 11.01 0 015.79 0c2.21-1.49 3.18-1.18 3.18-1.18.63 1.58.23 2.75.11 3.04.74.8 1.18 1.82 1.18 3.08 0 4.42-2.69 5.4-5.25 5.68.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .3.2.66.79.55A11.5 11.5 0 0023.5 12C23.5 5.65 18.35.5 12 .5z" />
  </svg>
);

const linkStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "4px 10px",
  fontSize: "0.8rem",
  fontWeight: 500,
  color: "#9ca3af",
  textDecoration: "none",
  borderRadius: 6,
  transition: "color 0.15s, background 0.15s",
};

const avatarStyle = {
  width: 28,
  height: 28,
  borderRadius: "50%",
  objectFit: "cover",
};

const initialAvatarStyle = {
  ...avatarStyle,
  background: "#4f46e5",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "0.75rem",
  fontWeight: 700,
  color: "#fff",
};

const logoutBtn = {
  background: "none",
  border: "none",
  color: "#6b7280",
  fontSize: "0.8rem",
  fontWeight: 500,
  cursor: "pointer",
  padding: "4px 8px",
  borderRadius: 6,
  transition: "color 0.15s",
};

export default function AuthButton({ user, onAuthChange }) {
  const slot = document.getElementById("auth-slot");
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = useCallback(async () => {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch {}
    onAuthChange(null);
    setLoggingOut(false);
  }, [onAuthChange]);

  if (!slot) return null;

  if (!user) {
    return createPortal(
      <>
        <a
          href="/api/auth/google/login"
          style={linkStyle}
          title="Sign in with Google"
          onMouseEnter={(e) => (e.currentTarget.style.color = "#fff")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#9ca3af")}
        >
          {googleIcon}
          <span>Google</span>
        </a>
        <a
          href="/api/auth/github/login"
          style={linkStyle}
          title="Sign in with GitHub"
          onMouseEnter={(e) => (e.currentTarget.style.color = "#fff")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#9ca3af")}
        >
          {githubIcon}
          <span>GitHub</span>
        </a>
      </>,
      slot
    );
  }

  const initial = (user.name || user.email || "?").trim().charAt(0).toUpperCase();

  return createPortal(
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {user.avatar_url ? (
        <img src={user.avatar_url} alt="" style={avatarStyle} />
      ) : (
        <div style={initialAvatarStyle}>{initial}</div>
      )}
      <span
        style={{
          fontSize: "0.8rem",
          fontWeight: 500,
          color: "#d1d5db",
          maxWidth: 120,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {user.name || user.email}
      </span>
      <button
        style={logoutBtn}
        onClick={handleLogout}
        disabled={loggingOut}
        onMouseEnter={(e) => (e.currentTarget.style.color = "#e5e7eb")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "#6b7280")}
      >
        {loggingOut ? "..." : "Logout"}
      </button>
    </div>,
    slot
  );
}
