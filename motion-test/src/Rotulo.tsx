import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { CORAL, INK, PAPER, YELLOW, display, mono } from "./theme";

export const Rotulo: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Rótulo" style={{ backgroundColor: YELLOW }}>
      <svg
        width={400}
        height={400}
        viewBox="0 0 400 400"
        style={{ position: "absolute", left: 760, top: 150, rotate: "-90deg" }}
      >
        <circle
          cx={200}
          cy={200}
          r={170}
          fill="none"
          stroke={INK}
          strokeWidth={30}
          strokeLinecap="round"
          strokeDasharray={1068.2}
          strokeDashoffset={interpolate(frame, [10, 40], [1068.2, 0], {
            easing: Easing.inOut(Easing.cubic),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })}
        />
      </svg>
      <Interactive.Div
        name="Triángulo"
        style={{
          position: "absolute",
          left: 905,
          top: 275,
          width: 135,
          height: 150,
          backgroundColor: CORAL,
          clipPath: "polygon(0 0, 100% 50%, 0 100%)",
          scale: interpolate(frame, [32, 48], [0, 1], {
            easing: Easing.out(Easing.back(1.7)),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />

      <Interactive.Div
        name="Placa"
        style={{
          position: "absolute",
          left: 140,
          top: 700,
          height: 160,
          overflow: "hidden",
          backgroundColor: INK,
          width: interpolate(frame, [44, 68], [0, 1060], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <Interactive.Div
          name="Nombre"
          style={{
            position: "absolute",
            left: 44,
            top: 30,
            whiteSpace: "nowrap",
            fontFamily: display,
            fontWeight: 800,
            fontSize: 84,
            lineHeight: 1.2,
            color: PAPER,
            translate: interpolate(frame, [52, 76], ["0px 140%", "0px 0%"], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Rótulo inferior
        </Interactive.Div>
      </Interactive.Div>
      <Interactive.Div
        name="Subplaca"
        style={{
          position: "absolute",
          left: 140,
          top: 860,
          height: 84,
          overflow: "hidden",
          backgroundColor: CORAL,
          width: interpolate(frame, [50, 74], [0, 880], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <Interactive.Div
          name="Detalle"
          style={{
            position: "absolute",
            left: 44,
            top: 12,
            whiteSpace: "nowrap",
            fontFamily: mono,
            fontWeight: 500,
            fontSize: 44,
            color: INK,
            opacity: interpolate(frame, [62, 76], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          LOWER THIRD · ENTRA EN 0,8 s
        </Interactive.Div>
      </Interactive.Div>
    </AbsoluteFill>
  );
};
