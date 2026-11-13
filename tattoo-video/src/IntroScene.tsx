import React from "react";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  random,
  useCurrentFrame,
} from "remotion";
import { Atmosphere, Backdrop, LogoCoin } from "./Shared";
import { BLOOD, BONE, body, display } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();

  const spin = interpolate(frame, [0, 55], [-900, 0], {
    ...clamp,
    easing: Easing.bezier(0.12, 0.8, 0.2, 1),
  });
  const float = Math.sin(frame / 14) * 14;
  const tilt = Math.cos(frame / 19) * 8;

  return (
    <AbsoluteFill>
      <Backdrop />

      {/* Ink droplets flying past the camera in depth */}
      <AbsoluteFill style={{ perspective: 900, transformStyle: "preserve-3d" }}>
        {new Array(46).fill(0).map((_, i) => {
          const x = (random(`x${i}`) - 0.5) * 2200;
          const y = (random(`y${i}`) - 0.5) * 3200;
          const z = ((random(`z${i}`) * 2400 + frame * 16) % 2400) - 1700;
          const s = 6 + random(`s${i}`) * 26;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: 540,
                top: 960,
                width: s,
                height: s,
                borderRadius: "50%",
                backgroundColor: i % 5 === 0 ? BLOOD : "#000",
                boxShadow: "0 0 0 1px rgba(255,255,255,0.08)",
                opacity: interpolate(z, [-1700, -1200, 500, 700], [0, 1, 1, 0], clamp),
                transform: `translate3d(${x}px, ${y}px, ${z}px)`,
              }}
            />
          );
        })}
      </AbsoluteFill>

      <AbsoluteFill
        name="Logo stage"
        style={{
          perspective: 1400,
          alignItems: "center",
          justifyContent: "center",
          paddingBottom: 380,
        }}
      >
        <div
          style={{
            transformStyle: "preserve-3d",
            scale: interpolate(frame, [0, 55], [0.15, 1], {
              ...clamp,
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            opacity: interpolate(frame, [0, 10], [0, 1], clamp),
          }}
        >
          <LogoCoin size={640} rotateY={spin + float} rotateX={tilt} />
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 330 }}
      >
        <div style={{ display: "flex", overflow: "hidden", perspective: 800 }}>
          {"TATTOO ART".split("").map((ch, i) => (
            <span
              key={i}
              style={{
                fontFamily: display,
                fontSize: 190,
                lineHeight: 1.1,
                color: BONE,
                letterSpacing: 4,
                display: "inline-block",
                width: ch === " " ? 50 : undefined,
                transformOrigin: "50% 100%",
                opacity: interpolate(frame, [42 + i * 3, 52 + i * 3], [0, 1], clamp),
                transform: `translateY(${interpolate(
                  frame,
                  [42 + i * 3, 62 + i * 3],
                  [160, 0],
                  { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) },
                )}px) rotateX(${interpolate(frame, [42 + i * 3, 62 + i * 3], [-80, 0], {
                  ...clamp,
                  easing: Easing.bezier(0.16, 1, 0.3, 1),
                })}deg)`,
              }}
            >
              {ch}
            </span>
          ))}
        </div>
        <Interactive.Div
          name="Red rule"
          style={{
            height: 6,
            width: 560,
            backgroundColor: "#c1121f",
            marginTop: 18,
            scale: interpolate(frame, [70, 92], ["0 1", "1 1"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        />
        <Interactive.Div
          name="Tagline"
          style={{
            fontFamily: body,
            fontSize: 44,
            color: "#f2ede4",
            marginTop: 40,
            letterSpacing: 2,
            opacity: interpolate(frame, [78, 98], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [78, 98], ["0px 30px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          Tu piel, nuestro lienzo
        </Interactive.Div>
      </AbsoluteFill>
      <Atmosphere />
    </AbsoluteFill>
  );
};
