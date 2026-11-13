import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { INK } from "./theme";

// Film grain + vignette that sit on top of every scene
export const Atmosphere: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at 50% 45%, transparent 45%, rgba(0,0,0,0.75) 100%)",
        }}
      />
      <svg width="100%" height="100%" style={{ opacity: 0.13, mixBlendMode: "overlay" }}>
        <filter id="grain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            seed={frame % 12}
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

export const Backdrop: React.FC<{ glow?: string }> = ({
  glow = "rgba(193,18,31,0.22)",
}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(circle at 50% 42%, ${glow} 0%, ${INK} 62%)`,
      backgroundColor: INK,
    }}
  />
);

// The logo as a thick 3D coin. Must live inside a parent with `perspective`.
export const LogoCoin: React.FC<{ size: number; rotateY: number; rotateX?: number }> = ({
  size,
  rotateY,
  rotateX = 0,
}) => {
  const layers = 14;
  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        transformStyle: "preserve-3d",
        transform: `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`,
      }}
    >
      {new Array(layers).fill(0).map((_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            background: i === layers - 1 ? "#0c0c0c" : "#2a2a2a",
            border: "3px solid #8d8d8d",
            transform: `translateZ(${-(i + 1) * 3}px)`,
            boxShadow:
              i === layers - 1 ? "0 0 120px rgba(255,255,255,0.12)" : undefined,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          overflow: "hidden",
          backfaceVisibility: "hidden",
          boxShadow: "0 0 0 3px #bdbdbd",
        }}
      >
        <Img
          src={staticFile("logo.png")}
          style={{ width: "100%", height: "100%", scale: "1.045" }}
        />
        {/* moving specular highlight */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(105deg, transparent 35%, rgba(255,255,255,0.28) 50%, transparent 65%)`,
            transform: `translateX(${rotateY * 4}px)`,
          }}
        />
      </div>
    </div>
  );
};

// A tattoo photo as a physical print with a glare that reacts to its angle
export const PhotoCard: React.FC<{
  file: string;
  width: number;
  height: number;
  glare?: number;
  dim?: number;
}> = ({ file, width, height, glare = 0, dim = 0 }) => (
  <div
    style={{
      width,
      height,
      position: "relative",
      borderRadius: 18,
      overflow: "hidden",
      backgroundColor: "#111",
      boxShadow:
        "0 0 0 2px rgba(242,237,228,0.35), 0 60px 120px rgba(0,0,0,0.75)",
    }}
  >
    <Img
      src={staticFile(file)}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
    <div
      style={{
        position: "absolute",
        inset: 0,
        background:
          "linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.22) 50%, transparent 70%)",
        transform: `translateX(${glare}%)`,
      }}
    />
    <div
      style={{ position: "absolute", inset: 0, backgroundColor: "#000", opacity: dim }}
    />
  </div>
);
