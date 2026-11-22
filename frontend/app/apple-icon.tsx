import { ImageResponse } from "next/og";

// The home-screen icon (#80), drawn from the same mark as app/icon.svg. iOS adds
// its own rounded corners, so this one is a full square.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#0b2545" }}>
        <svg width="180" height="180" viewBox="0 0 32 32">
          <path d="M8 25 C 8 16, 20 20, 20 11" fill="none" stroke="#8ecae6" strokeWidth="4" strokeLinecap="round" />
          <circle cx="22.5" cy="8.5" r="4" fill="#ffffff" />
        </svg>
      </div>
    ),
    size,
  );
}
