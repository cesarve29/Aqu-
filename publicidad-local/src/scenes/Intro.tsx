import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  CanvasImage,
  Easing,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { brand } from "../brand";
import { Background } from "../components/Background";
import { bodyFont, displayFont } from "../fonts";

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Intro">
      <Background tone="dark" centerY={690} />

      <Interactive.Div
        name="Onda"
        style={{
          position: "absolute",
          left: 90,
          top: 240,
          width: 900,
          height: 900,
          borderRadius: "50%",
          border: `22px solid ${brand.colors.yellow}`,
          boxSizing: "border-box",
          scale: interpolate(frame, [8, 40], [0.3, 2.6], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          opacity: interpolate(frame, [8, 14, 40], [0, 0.9, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />

      <CanvasImage
        name="Logo"
        src={staticFile("logo.png")}
        width={800}
        height={800}
        style={{
          position: "absolute",
          left: 140,
          top: 290,
          filter: "drop-shadow(0px 30px 60px rgba(0,0,0,0.6))",
          scale: interpolate(frame, [2, 30, 100], [0, 1, 1.08], {
            easing: [Easing.spring({ damping: 9 }), Easing.linear],
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: interpolate(frame, [2, 30], ["-40deg", "0deg"], {
            easing: Easing.spring({ damping: 11 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />

      <Interactive.Div
        name="Línea 1"
        style={{
          position: "absolute",
          left: 0,
          top: 1140,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 150,
          lineHeight: 1,
          letterSpacing: 4,
          color: brand.colors.yellow,
          textShadow: `8px 8px 0px ${brand.colors.red}`,
          translate: interpolate(frame, [22, 42], ["-1100px 0px", "0px 0px"], {
            easing: Easing.spring({ damping: 15 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-3deg",
        }}
      >
        PERROS CALIENTES
      </Interactive.Div>

      <Interactive.Div
        name="Línea 2"
        style={{
          position: "absolute",
          left: 0,
          top: 1290,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 150,
          lineHeight: 1,
          letterSpacing: 4,
          color: brand.colors.light,
          textShadow: `8px 8px 0px ${brand.colors.red}`,
          translate: interpolate(frame, [28, 48], ["1100px 0px", "0px 0px"], {
            easing: Easing.spring({ damping: 15 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-3deg",
        }}
      >
        & HAMBURGUESAS
      </Interactive.Div>

      <Interactive.Div
        name="Eslogan"
        style={{
          position: "absolute",
          left: 0,
          top: 1480,
          width: 1080,
          display: "flex",
          justifyContent: "center",
          scale: interpolate(frame, [42, 60], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      >
        <div
          style={{
            fontFamily: bodyFont,
            fontWeight: 800,
            fontSize: 52,
            color: brand.colors.dark,
            backgroundColor: brand.colors.yellow,
            padding: "16px 46px",
            borderRadius: 999,
          }}
        >
          {brand.slogan}
        </div>
      </Interactive.Div>
      <Audio
        name="SFX entrada logo"
        from={0}
        src={staticFile("sfx/swish.wav")}
        volume={0.36}
      />
      <Audio
        name="SFX golpe logo"
        from={7}
        src={staticFile("sfx/impact.wav")}
        volume={0.72}
      />
      <Audio
        name="SFX línea 1"
        from={22}
        src={staticFile("sfx/swish.wav")}
        volume={0.32}
      />
      <Audio
        name="SFX línea 2"
        from={28}
        src={staticFile("sfx/swish.wav")}
        volume={0.32}
      />
      <Audio
        name="SFX eslogan"
        from={43}
        src={staticFile("sfx/pop.wav")}
        volume={0.43}
      />
    </AbsoluteFill>
  );
};
