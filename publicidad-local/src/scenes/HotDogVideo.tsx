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

const STAR =
  "polygon(50% 0%, 61% 12%, 77% 7%, 80% 23%, 96% 27%, 89% 42%, 100% 55%, 87% 64%, 90% 81%, 74% 81%, 66% 96%, 50% 87%, 34% 96%, 26% 81%, 10% 81%, 13% 64%, 0% 55%, 11% 42%, 4% 27%, 20% 23%, 23% 7%, 39% 12%)";

export const HotDogVideo: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Perros video" style={{ backgroundColor: "#140E0E" }}>
      <Video
        name="Video perros"
        src={staticFile("videos/perros.mp4")}
        muted
        trimBefore={12}
        playbackRate={1.5}
        objectFit="cover"
        style={{
          position: "absolute",
          width: 1080,
          height: 1920,
          scale: interpolate(frame, [0, 110], [1.12, 1], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      />
      <AbsoluteFill
        name="Degradado"
        style={{
          background:
            "linear-gradient(180deg, rgba(20,14,14,0.92) 0%, rgba(20,14,14,0.55) 24%, rgba(20,14,14,0) 44%, rgba(20,14,14,0) 70%, rgba(20,14,14,0.75) 100%)",
        }}
      />

      <Interactive.Div
        name="Título 1"
        style={{
          position: "absolute",
          left: 70,
          top: 210,
          fontFamily: displayFont,
          fontSize: 230,
          lineHeight: 0.95,
          letterSpacing: 5,
          color: brand.colors.yellow,
          textShadow: `10px 10px 0px ${brand.colors.red}`,
          translate: interpolate(frame, [10, 30], ["-1100px 0px", "0px 0px"], {
            easing: Easing.spring({ damping: 15 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-4deg",
        }}
      >
        PERROS
      </Interactive.Div>
      <Interactive.Div
        name="Título 2"
        style={{
          position: "absolute",
          left: 70,
          top: 420,
          fontFamily: displayFont,
          fontSize: 190,
          lineHeight: 0.95,
          letterSpacing: 5,
          color: brand.colors.light,
          textShadow: `10px 10px 0px ${brand.colors.red}`,
          translate: interpolate(frame, [15, 35], ["-1100px 0px", "0px 0px"], {
            easing: Easing.spring({ damping: 15 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-4deg",
        }}
      >
        CALIENTES
      </Interactive.Div>

      <Interactive.Div
        name="Precio"
        style={{
          position: "absolute",
          left: 462,
          top: 960,
          width: 540,
          height: 540,
          filter: "drop-shadow(0px 24px 30px rgba(0,0,0,0.55))",
          scale: interpolate(
            frame,
            [30, 48, 70, 78, 86, 110],
            [0, 1, 1, 1.1, 1, 1.04],
            {
              easing: [
                Easing.spring({ damping: 8 }),
                Easing.linear,
                Easing.inOut(Easing.quad),
                Easing.inOut(Easing.quad),
                Easing.linear,
              ],
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              output: "perceptual-scale",
            },
          ),
          rotate: interpolate(
            frame,
            [30, 48, 110],
            ["-80deg", "10deg", "4deg"],
            {
              easing: [Easing.spring({ damping: 11 }), Easing.linear],
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
        }}
      >
        <div
          style={{
            width: 540,
            height: 540,
            clipPath: STAR,
            backgroundColor: brand.colors.red,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontFamily: bodyFont,
              fontWeight: 800,
              fontSize: 54,
              lineHeight: 1,
              color: brand.colors.light,
            }}
          >
            DESDE
          </div>
          <div
            style={{
              fontFamily: displayFont,
              fontSize: 168,
              lineHeight: 1.05,
              letterSpacing: 3,
              color: brand.colors.yellow,
              textShadow: `6px 6px 0px ${brand.colors.dark}`,
            }}
          >
            {brand.priceFrom}
          </div>
        </div>
      </Interactive.Div>
      <Audio
        name="SFX transición"
        from={3}
        src={staticFile("sfx/whoosh.wav")}
        volume={0.78}
      />
      <Audio
        name="SFX título 1"
        from={11}
        src={staticFile("sfx/swish.wav")}
        volume={0.39}
      />
      <Audio
        name="SFX título 2"
        from={16}
        src={staticFile("sfx/swish.wav")}
        volume={0.39}
      />
      <Audio
        name="SFX sello"
        from={32}
        src={staticFile("sfx/thud.wav")}
        volume={0.88}
      />
      <Audio
        name="SFX sello pop"
        from={33}
        src={staticFile("sfx/pop.wav")}
        volume={0.54}
      />
      <Audio
        name="SFX pulso"
        from={71}
        src={staticFile("sfx/pop.wav")}
        volume={0.39}
      />
    </AbsoluteFill>
  );
};
