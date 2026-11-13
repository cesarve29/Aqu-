import React from "react";
import { Video } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Atmosphere, Backdrop } from "./Shared";
import { BONE, display } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const W = 760;
const H = 1350;

// Studio footage playing on a slab that swings in 3D space
export const ProcessScene: React.FC = () => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 26], [1, 0], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const rotY = interpolate(frame, [0, 150], [-20, 20]) + enter * -70;
  const rotX = interpolate(frame, [0, 150], [7, -5]);

  return (
    <AbsoluteFill>
      <Backdrop glow="rgba(193,18,31,0.28)" />

      <AbsoluteFill
        name="Video stage"
        style={{
          perspective: 1500,
          alignItems: "center",
          justifyContent: "center",
          paddingTop: 200,
        }}
      >
        <div
          style={{
            position: "relative",
            width: W,
            height: H,
            transformStyle: "preserve-3d",
            transform: `translateZ(${-enter * 900}px) rotateX(${rotX}deg) rotateY(${rotY}deg)`,
          }}
        >
          {/* slab thickness */}
          {new Array(8).fill(0).map((_, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: 34,
                backgroundColor: "#1c1c1c",
                border: "2px solid #6f6f6f",
                transform: `translateZ(${-(i + 1) * 4}px)`,
              }}
            />
          ))}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 34,
              overflow: "hidden",
              backgroundColor: "#000",
              boxShadow: "0 0 0 3px rgba(242,237,228,0.5), 0 80px 160px rgba(0,0,0,0.8)",
            }}
          >
            <Video
              src={staticFile("process.mp4")}
              muted
              objectFit="cover"
              style={{ width: W, height: H }}
            />
            <div
              style={{
                position: "absolute",
                inset: 0,
                background:
                  "linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.16) 50%, transparent 70%)",
                transform: `translateX(${-rotY * 5}%)`,
              }}
            />
          </div>
          {/* floating REC tag for parallax */}
          <div
            style={{
              position: "absolute",
              top: 40,
              left: -30,
              transform: "translateZ(140px)",
              display: "flex",
              alignItems: "center",
              gap: 16,
              backgroundColor: "#c1121f",
              color: BONE,
              fontFamily: display,
              fontSize: 54,
              letterSpacing: 4,
              padding: "6px 26px",
            }}
          >
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                backgroundColor: BONE,
                opacity: Math.floor(frame / 15) % 2 === 0 ? 1 : 0.25,
              }}
            />
            EN SESIÓN
          </div>
        </div>
      </AbsoluteFill>

      <AbsoluteFill style={{ alignItems: "center", paddingTop: 130 }}>
        <Interactive.Div
          name="Headline"
          style={{
            fontFamily: display,
            fontSize: 132,
            color: "#f2ede4",
            letterSpacing: 6,
            opacity: interpolate(frame, [8, 24], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [8, 28], ["0px -60px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          EL PROCESO
        </Interactive.Div>
      </AbsoluteFill>
      <Atmosphere />
    </AbsoluteFill>
  );
};
