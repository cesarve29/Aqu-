import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CORAL, INK, PAPER, YELLOW, clamp, mono } from "./theme";

const COLS = 6;
const ROWS = 3;
const CELL = 210;
const SIZE = 130;
const COLORS = [INK, PAPER, YELLOW];

export const Formas: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const shapes = [];
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const dx = i - (COLS - 1) / 2;
      const dy = j - (ROWS - 1) / 2;
      const d = Math.sqrt(dx * dx + dy * dy);
      // Entrada escalonada desde el centro hacia fuera.
      const pop = interpolate(frame, [10 + d * 3, 28 + d * 3], [0, 1], {
        ...clamp,
        easing: Easing.out(Easing.back(1.7)),
      });
      // 0 = cuadrado, 1 = círculo.
      const morph = (Math.sin(t * 2.2 - d * 0.7) + 1) / 2;
      shapes.push(
        <div
          key={`${i}-${j}`}
          style={{
            position: "absolute",
            left: 960 + dx * CELL - SIZE / 2,
            top: 450 + dy * CELL - SIZE / 2,
            width: SIZE,
            height: SIZE,
            backgroundColor: COLORS[(i + j) % 3],
            borderRadius: `${morph * 50}%`,
            scale: String(pop),
            rotate: `${Math.sin(t * 1.4 - d * 0.5) * 45}deg`,
          }}
        />,
      );
    }
  }

  return (
    <AbsoluteFill name="Formas" style={{ backgroundColor: CORAL }}>
      {shapes}
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 900,
          overflow: "hidden",
        }}
      >
        <Interactive.Div
          name="Etiqueta"
          style={{
            fontFamily: mono,
            fontWeight: 500,
            fontSize: 44,
            color: INK,
            translate: interpolate(frame, [30, 52], ["0px 110%", "0px 0%"], {
              easing: Easing.bezier(0.16, 1, 0.3, 1),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          FORMAS · ENTRADA ESCALONADA · 18 PIEZAS
        </Interactive.Div>
      </div>
    </AbsoluteFill>
  );
};
