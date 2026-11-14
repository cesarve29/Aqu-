import {
  AbsoluteFill,
  Interactive,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { brand } from "../brand";

export type Tone = "dark" | "red" | "yellow";

const palette: Record<Tone, { base: string; ray: string; dot: string }> = {
  dark: {
    base: brand.colors.dark,
    ray: "rgba(227,27,35,0.30)",
    dot: "rgba(255,221,23,0.07)",
  },
  red: {
    base: brand.colors.red,
    ray: "rgba(255,221,23,0.16)",
    dot: "rgba(0,0,0,0.14)",
  },
  yellow: {
    base: brand.colors.yellow,
    ray: "rgba(255,255,255,0.34)",
    dot: "rgba(227,27,35,0.15)",
  },
};

export const Background: React.FC<{ tone: Tone; centerY?: number }> = ({
  tone,
  centerY = 760,
}) => {
  const frame = useCurrentFrame();
  const colors = palette[tone];

  return (
    <AbsoluteFill style={{ backgroundColor: colors.base, overflow: "hidden" }}>
      <Interactive.Div
        name="Rayos"
        style={{
          position: "absolute",
          width: 3400,
          height: 3400,
          left: -1160,
          top: centerY - 1700,
          background: `repeating-conic-gradient(${colors.ray} 0deg 9deg, transparent 9deg 18deg)`,
          rotate: interpolate(frame, [0, 300], ["0deg", "80deg"]),
        }}
      />
      <Interactive.Div
        name="Puntos"
        style={{
          position: "absolute",
          inset: -100,
          backgroundImage: `radial-gradient(circle, ${colors.dot} 24%, transparent 26%)`,
          backgroundSize: "46px 46px",
          translate: interpolate(frame, [0, 300], ["0px 0px", "46px 92px"]),
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at 50% 42%, transparent 46%, rgba(0,0,0,0.45) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
