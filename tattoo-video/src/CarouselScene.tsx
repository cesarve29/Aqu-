import React from "react";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { Atmosphere, Backdrop, PhotoCard } from "./Shared";
import { BONE, PIECES, body, display } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const STEP = 20; // frames each piece holds the front spot
const R = 980;
const CARD_W = 620;
const CARD_H = 940;

export const CarouselScene: React.FC = () => {
  const frame = useCurrentFrame();
  const n = PIECES.length;
  const slice = 360 / n;

  // Stepped rotation: snap card to card with an eased whip between them
  const t = frame / STEP;
  const whole = Math.floor(t);
  const eased = Easing.bezier(0.75, 0, 0.2, 1)(t - whole);
  const turn = (whole + eased) * slice;
  const active = Math.round(turn / slice) % n;

  return (
    <AbsoluteFill>
      <Backdrop glow="rgba(242,237,228,0.10)" />

      <AbsoluteFill
        name="Carousel stage"
        style={{
          perspective: 1700,
          perspectiveOrigin: "50% 46%",
          alignItems: "center",
          justifyContent: "center",
          opacity: interpolate(frame, [0, 12], [0, 1], clamp),
        }}
      >
        <div
          style={{
            width: CARD_W,
            height: CARD_H,
            position: "relative",
            transformStyle: "preserve-3d",
            transform: `translateZ(${-R - interpolate(frame, [0, 40], [1400, 0], {
              ...clamp,
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            })}px) rotateX(${interpolate(frame, [0, 180], [-10, -3])}deg) rotateY(${-turn}deg)`,
          }}
        >
          {PIECES.map((p, i) => {
            const rel = ((i * slice - turn + 540) % 360) - 180; // angle to camera
            const facing = Math.cos((rel * Math.PI) / 180);
            return (
              <div
                key={p.file}
                style={{
                  position: "absolute",
                  inset: 0,
                  backfaceVisibility: "hidden",
                  transform: `rotateY(${i * slice}deg) translateZ(${R}px)`,
                }}
              >
                <PhotoCard
                  file={p.file}
                  width={CARD_W}
                  height={CARD_H}
                  glare={rel * 3}
                  dim={interpolate(facing, [0.3, 1], [0.8, 0], clamp)}
                />
              </div>
            );
          })}
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
          NUESTRO TRABAJO
        </Interactive.Div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 170 }}
      >
        <div
          style={{
            fontFamily: body,
            fontWeight: 700,
            fontSize: 50,
            color: BONE,
            letterSpacing: 6,
            textTransform: "uppercase",
            opacity: interpolate(frame, [14, 28], [0, 1], clamp),
          }}
        >
          {PIECES[active].style}
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 34 }}>
          {PIECES.map((p, i) => (
            <div
              key={p.file}
              style={{
                width: i === active ? 64 : 18,
                height: 8,
                borderRadius: 4,
                backgroundColor: i === active ? "#c1121f" : "rgba(242,237,228,0.35)",
              }}
            />
          ))}
        </div>
      </AbsoluteFill>
      <Atmosphere />
    </AbsoluteFill>
  );
};
