import { Audio, Video } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { brand } from "../brand";
import { bodyFont, displayFont } from "../fonts";

export const BurgerVideo: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill
      name="Hamburguesa video"
      style={{ backgroundColor: "#140E0E" }}
    >
      <Video
        name="Video hamburguesa"
        src={staticFile("videos/hamburguesa.mp4")}
        muted
        trimBefore={231}
        objectFit="cover"
        style={{ position: "absolute", width: 1080, height: 1920 }}
      />
      <AbsoluteFill
        name="Degradado"
        style={{
          background:
            "linear-gradient(180deg, rgba(20,14,14,0.94) 0%, rgba(20,14,14,0.6) 22%, rgba(20,14,14,0) 40%, rgba(20,14,14,0) 78%, rgba(20,14,14,0.7) 100%)",
        }}
      />

      <Interactive.Div
        name="Título"
        style={{
          position: "absolute",
          left: 0,
          top: 215,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 176,
          lineHeight: 1,
          letterSpacing: 4,
          color: brand.colors.yellow,
          textShadow: `9px 9px 0px ${brand.colors.red}`,
          scale: interpolate(frame, [10, 30], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: "-3deg",
        }}
      >
        HAMBURGUESAS
      </Interactive.Div>

      <Interactive.Div
        name="Subtítulo"
        style={{
          position: "absolute",
          left: 0,
          top: 430,
          width: 1080,
          display: "flex",
          justifyContent: "center",
          translate: interpolate(frame, [22, 42], ["1100px 0px", "0px 0px"], {
            easing: Easing.spring({ damping: 15 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-3deg",
        }}
      >
        <div
          style={{
            fontFamily: bodyFont,
            fontWeight: 800,
            fontSize: 58,
            color: brand.colors.light,
            backgroundColor: brand.colors.red,
            padding: "14px 44px",
            borderRadius: 999,
          }}
        >
          ¡Para comer como loco!
        </div>
      </Interactive.Div>
      <Audio
        name="SFX transición"
        from={3}
        src={staticFile("sfx/whoosh.wav")}
        volume={0.68}
      />
      <Audio
        name="SFX título"
        from={11}
        src={staticFile("sfx/thud.wav")}
        volume={0.65}
      />
      <Audio
        name="SFX título pop"
        from={11}
        src={staticFile("sfx/pop.wav")}
        volume={0.41}
      />
      <Audio
        name="SFX subtítulo"
        from={23}
        src={staticFile("sfx/swish.wav")}
        volume={0.43}
      />
    </AbsoluteFill>
  );
};
