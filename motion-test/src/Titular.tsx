import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { CORAL, INK, PAPER, TEAL, YELLOW, display, mono } from "./theme";

export const Titular: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Titular" style={{ backgroundColor: INK }}>
      <Interactive.Div
        name="Círculo"
        style={{
          position: "absolute",
          left: 1500,
          top: 90,
          width: 260,
          height: 260,
          borderRadius: "50%",
          backgroundColor: YELLOW,
          scale: interpolate(frame, [8, 30], [0, 1], {
            easing: Easing.out(Easing.back(1.7)),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          translate: interpolate(
            frame,
            [0, 135],
            ["0px 14px", "0px -14px"],
            { easing: Easing.inOut(Easing.sin) },
          ),
        }}
      />
      <svg
        width={260}
        height={260}
        viewBox="0 0 260 260"
        style={{ position: "absolute", left: 1560, top: 720, rotate: "-90deg" }}
      >
        <circle
          cx={130}
          cy={130}
          r={110}
          fill="none"
          stroke={TEAL}
          strokeWidth={24}
          strokeDasharray={691.2}
          strokeDashoffset={interpolate(frame, [16, 46], [691.2, 0], {
            easing: Easing.out(Easing.cubic),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })}
        />
      </svg>
      <Interactive.Div
        name="Cuadrado"
        style={{
          position: "absolute",
          left: 1330,
          top: 820,
          width: 96,
          height: 96,
          backgroundColor: CORAL,
          scale: interpolate(frame, [18, 38], [0, 1], {
            easing: Easing.out(Easing.back(1.7)),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: interpolate(frame, [0, 135], ["0deg", "180deg"]),
        }}
      />

      <div
        style={{
          position: "absolute",
          left: 140,
          top: 330,
          fontFamily: display,
          fontWeight: 800,
          fontSize: 146,
          lineHeight: 1.12,
          letterSpacing: "-0.02em",
          whiteSpace: "nowrap",
        }}
      >
        <div style={{ overflow: "hidden" }}>
          <Interactive.Div
            name="Línea 1"
            style={{
              color: PAPER,
              translate: interpolate(frame, [8, 36], ["0px 110%", "0px 0%"], {
                easing: Easing.bezier(0.16, 1, 0.3, 1),
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            GRÁFICOS EN
          </Interactive.Div>
        </div>
        <div style={{ overflow: "hidden" }}>
          <Interactive.Div
            name="Línea 2"
            style={{
              color: YELLOW,
              translate: interpolate(frame, [13, 41], ["0px 110%", "0px 0%"], {
                easing: Easing.bezier(0.16, 1, 0.3, 1),
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            MOVIMIENTO
          </Interactive.Div>
        </div>
      </div>

      <Interactive.Div
        name="Barra"
        style={{
          position: "absolute",
          left: 140,
          top: 700,
          height: 18,
          backgroundColor: CORAL,
          width: interpolate(frame, [28, 56], [0, 1240], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
      <Interactive.Div
        name="Etiqueta"
        style={{
          position: "absolute",
          left: 140,
          top: 760,
          fontFamily: mono,
          fontWeight: 500,
          fontSize: 44,
          color: PAPER,
          opacity: interpolate(frame, [42, 58], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        PRUEBA 01 · 16 s · 30 fps
      </Interactive.Div>
    </AbsoluteFill>
  );
};
