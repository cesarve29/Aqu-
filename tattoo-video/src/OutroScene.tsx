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
          paddingBottom: 420,
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
            size={560}
            rotateY={land + Math.sin(frame / 16) * 16}
            rotateX={Math.cos(frame / 21) * 7}
          />
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{ alignItems: "center", justifyContent: "flex-end", paddingBottom: 300 }}
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
          name="Sign-off"
          style={{
            fontFamily: body,
            fontWeight: 700,
            fontSize: 44,
            color: "#f2ede4",
            backgroundColor: "#c1121f",
            padding: "16px 40px",
            marginTop: 40,
            letterSpacing: 4,
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
          TINTA QUE CUENTA HISTORIAS
        </Interactive.Div>
      </AbsoluteFill>
      <Atmosphere />
    </AbsoluteFill>
  );
};
