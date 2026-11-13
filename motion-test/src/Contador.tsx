import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { INK, PAPER, TEAL, YELLOW, clamp, display, mono } from "./theme";

const BARS = [0.35, 0.55, 0.45, 0.7, 0.6, 0.85, 1];

export const Contador: React.FC = () => {
  const frame = useCurrentFrame();

  const value = Math.round(
    interpolate(frame, [14, 80], [0, 480], {
      ...clamp,
      easing: Easing.out(Easing.cubic),
    }),
  );
  const digits = String(value).padStart(3, "0").split("");

  return (
    <AbsoluteFill name="Contador" style={{ backgroundColor: TEAL }}>
      <div
        style={{
          position: "absolute",
          left: 130,
          top: 210,
          overflow: "hidden",
        }}
      >
        <Interactive.Div
          name="Cifra"
          style={{
            display: "flex",
            fontFamily: display,
            fontWeight: 800,
            fontSize: 280,
            lineHeight: 1.1,
            color: PAPER,
            translate: interpolate(frame, [8, 32], ["0px 110%", "0px 0%"], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {digits.map((digit, i) => (
            // Ancho fijo por dígito para que la cifra no tiemble al contar.
            <span key={i} style={{ width: 286, textAlign: "center" }}>
              {digit}
            </span>
          ))}
        </Interactive.Div>
      </div>

      <div
        style={{ position: "absolute", left: 140, top: 540, overflow: "hidden" }}
      >
        <Interactive.Div
          name="Unidad"
          style={{
            fontFamily: display,
            fontWeight: 500,
            fontSize: 84,
            lineHeight: 1.4,
            color: INK,
            translate: interpolate(frame, [18, 42], ["0px 110%", "0px 0%"], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          fotogramas
        </Interactive.Div>
      </div>
      <Interactive.Div
        name="Cálculo"
        style={{
          position: "absolute",
          left: 140,
          top: 700,
          fontFamily: mono,
          fontWeight: 500,
          fontSize: 46,
          color: PAPER,
          opacity: interpolate(frame, [30, 46], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        16 s × 30 fps = 480
      </Interactive.Div>

      <div
        style={{
          position: "absolute",
          left: 1040,
          top: 300,
          width: 740,
          height: 520,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
        }}
      >
        {BARS.map((h, i) => (
          <div
            key={i}
            style={{
              width: 76,
              backgroundColor: i === BARS.length - 1 ? YELLOW : PAPER,
              height: interpolate(
                frame,
                [18 + i * 3, 40 + i * 3],
                [0, h * 500],
                { ...clamp, easing: Easing.out(Easing.back(1.4)) },
              ),
            }}
          />
        ))}
      </div>
      <Interactive.Div
        name="Línea base"
        style={{
          position: "absolute",
          left: 1020,
          top: 820,
          height: 8,
          backgroundColor: INK,
          width: interpolate(frame, [10, 36], [0, 780], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
    </AbsoluteFill>
  );
};
