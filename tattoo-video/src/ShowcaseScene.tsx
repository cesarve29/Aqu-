import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Atmosphere, PhotoCard } from "./Shared";
import { BLOOD, BONE, INK, PIECES, Piece, body, display } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const SLIDE = 50;
export const FEATURED = [0, 2, 4, 1, 3].map((i) => PIECES[i]);

const Slide: React.FC<{ piece: Piece; index: number }> = ({ piece, index }) => {
  const frame = useCurrentFrame();
  const dir = index % 2 === 0 ? 1 : -1;

  const maxW = 880;
  const maxH = 1300;
  const k = Math.min(maxW / piece.w, maxH / piece.h);
  const w = piece.w * k;
  const h = piece.h * k;

  const enter = interpolate(frame, [0, 18], [1, 0], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const exit = interpolate(frame, [SLIDE - 8, SLIDE], [0, 1], {
    ...clamp,
    easing: Easing.bezier(0.7, 0, 0.84, 0),
  });
  const swing = interpolate(frame, [0, SLIDE], [16, -16]) * dir;
  const rotY = swing + enter * 85 * dir - exit * 85 * dir;
  const rotX = interpolate(frame, [0, SLIDE], [5, -4]);

  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      {/* far layer: blurred, slow-moving copy of the piece */}
      <AbsoluteFill
        style={{
          opacity: 0.45 * (1 - exit) * (1 - enter),
          transform: `scale(1.5) translateX(${swing * 2.2}px)`,
          filter: "blur(40px) saturate(0.6)",
        }}
      >
        <Img
          src={staticFile(piece.file)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          perspective: 1500,
          alignItems: "center",
          justifyContent: "center",
          paddingBottom: 120,
        }}
      >
        <div
          style={{
            position: "relative",
            width: w,
            height: h,
            transformStyle: "preserve-3d",
            transform: `translateZ(${-enter * 600 - exit * 600}px) rotateX(${rotX}deg) rotateY(${rotY}deg)`,
            opacity: 1 - exit,
          }}
        >
          <PhotoCard file={piece.file} width={w} height={h} glare={-swing * 5} />

          {/* frame floating in front of the print */}
          <div
            style={{
              position: "absolute",
              inset: -26,
              border: `3px solid ${BONE}`,
              borderRadius: 30,
              opacity: 0.55,
              transform: "translateZ(70px)",
            }}
          />

          {/* label floating even closer to camera → strong parallax */}
          <div
            style={{
              position: "absolute",
              left: dir === 1 ? 40 : undefined,
              right: dir === -1 ? 40 : undefined,
              bottom: -90,
              transform: "translateZ(170px)",
              textAlign: dir === 1 ? "left" : "right",
            }}
          >
            <div
              style={{
                fontFamily: body,
                fontWeight: 700,
                fontSize: 44,
                color: BONE,
                backgroundColor: BLOOD,
                display: "inline-block",
                padding: "8px 22px",
                letterSpacing: 3,
              }}
            >
              0{index + 1}
            </div>
            <div
              style={{
                fontFamily: display,
                fontSize: 150,
                lineHeight: 1.05,
                color: BONE,
                textTransform: "uppercase",
                whiteSpace: "nowrap",
                textShadow: "0 12px 40px rgba(0,0,0,0.9)",
              }}
            >
              {piece.style}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const ShowcaseScene: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: INK }}>
    {FEATURED.map((p, i) => (
      <Sequence key={p.file} name={p.style} from={i * SLIDE} durationInFrames={SLIDE}>
        <Slide piece={p} index={i} />
      </Sequence>
    ))}
    <Atmosphere />
  </AbsoluteFill>
);
