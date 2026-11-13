import React from "react";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  random,
  useCurrentFrame,
} from "remotion";
import { Atmosphere, Backdrop, LogoCoin, PhotoCard } from "./Shared";
import { PIECES, body, display } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const land = interpolate(frame, [10, 50], [540, 0], {
    ...clamp,
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill>
      <Backdrop />

      {/* Tunnel of prints drifting past the camera */}
      <AbsoluteFill style={{ perspective: 1100, transformStyle: "preserve-3d" }}>
        {PIECES.concat(PIECES).map((p, i) => {
          const a = (i / 18) * Math.PI * 2 * 2.6;
          const x = Math.cos(a) * 760;
          const y = Math.sin(a) * 1150;
          const z = ((i * 260 + frame * 14) % 4680) - 4200;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: 540 - 190,
                top: 960 - 290,
                opacity: interpolate(z, [-4200, -3200, 100, 480], [0, 1, 1, 0], clamp),
                transform: `translate3d(${x}px, ${y}px, ${z}px) rotateY(${
                  -Math.cos(a) * 32
                }deg) rotateZ(${(random(`r${i}`) - 0.5) * 14}deg)`,
              }}
            >
              <PhotoCard file={p.file} width={380} height={580} dim={0.3} />
            </div>
          );
        })}
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 50% 46%, rgba(7,7,7,0.88) 0%, rgba(7,7,7,0.55) 45%, transparent 75%)",
        }}
      />

      <AbsoluteFill
        name="Logo stage"
        style={{
          perspective: 1400,
          alignItems: "center",
          justifyContent: "center",
          paddingBottom: 760,
        }}
      >
        <div
          style={{
            transformStyle: "preserve-3d",
            scale: interpolate(frame, [10, 50], [0.3, 1], {
              ...clamp,
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            opacity: interpolate(frame, [10, 22], [0, 1], clamp),
          }}
        >
          <LogoCoin
            size={470}
            rotateY={land + Math.sin(frame / 16) * 16}
            rotateX={Math.cos(frame / 21) * 7}
          />
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 230 }}
      >
        <Interactive.Div
          name="Call to action"
          style={{
            fontFamily: display,
            fontSize: 170,
            lineHeight: 1.05,
            color: "#f2ede4",
            textAlign: "center",
            letterSpacing: 4,
            opacity: interpolate(frame, [40, 56], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            scale: interpolate(frame, [40, 62], [1.35, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              output: "perceptual-scale",
            }),
          }}
        >
          AGENDA TU CITA
        </Interactive.Div>
        <Interactive.Div
          name="Instagram"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            fontFamily: body,
            fontWeight: 700,
            fontSize: 54,
            color: "#f2ede4",
            marginTop: 50,
            opacity: interpolate(frame, [58, 72], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [58, 76], ["0px 40px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <svg width="68" height="68" viewBox="0 0 24 24" fill="none" stroke="#f2ede4" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="5" />
            <circle cx="12" cy="12" r="4.2" />
            <circle cx="17.3" cy="6.7" r="1" fill="#f2ede4" stroke="none" />
          </svg>
          @diegoerojastattoo
        </Interactive.Div>
        <Interactive.Div
          name="Phone"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            fontFamily: body,
            fontWeight: 700,
            fontSize: 62,
            color: "#f2ede4",
            backgroundColor: "#c1121f",
            padding: "18px 44px",
            marginTop: 36,
            letterSpacing: 3,
            opacity: interpolate(frame, [68, 82], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [68, 86], ["0px 40px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <svg width="58" height="58" viewBox="0 0 24 24" fill="#f2ede4">
            <path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1L6.6 10.8z" />
          </svg>
          312 494 0807
        </Interactive.Div>
      </AbsoluteFill>
      <Atmosphere />
    </AbsoluteFill>
  );
};
