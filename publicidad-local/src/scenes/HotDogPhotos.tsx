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
import { displayFont } from "../fonts";

export const HotDogPhotos: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Perros fotos">
      <Background tone="red" centerY={980} />

      <Interactive.Div
        name="Título 1"
        style={{
          position: "absolute",
          left: 0,
          top: 215,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 170,
          lineHeight: 1,
          letterSpacing: 5,
          color: brand.colors.light,
          textShadow: `9px 9px 0px ${brand.colors.dark}`,
          scale: interpolate(frame, [8, 26], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: "-3deg",
        }}
      >
        ¡BIEN
      </Interactive.Div>
      <Interactive.Div
        name="Título 2"
        style={{
          position: "absolute",
          left: 0,
          top: 370,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 210,
          lineHeight: 1,
          letterSpacing: 5,
          color: brand.colors.yellow,
          textShadow: `10px 10px 0px ${brand.colors.dark}`,
          scale: interpolate(frame, [14, 32], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: "-3deg",
        }}
      >
        CARGADOS!
      </Interactive.Div>

      <Interactive.Div
        name="Foto bandeja"
        style={{
          position: "absolute",
          left: 60,
          top: 640,
          width: 580,
          height: 768,
          borderRadius: 40,
          border: `14px solid ${brand.colors.light}`,
          boxSizing: "border-box",
          overflow: "hidden",
          boxShadow: "0px 36px 60px rgba(0,0,0,0.5)",
          translate: interpolate(
            frame,
            [6, 30, 93],
            ["-800px 500px", "0px 0px", "10px -22px"],
            {
              easing: [Easing.spring({ damping: 14 }), Easing.linear],
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
          rotate: interpolate(
            frame,
            [6, 30, 93],
            ["-30deg", "-6deg", "-4deg"],
            {
              easing: [Easing.spring({ damping: 12 }), Easing.linear],
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
        }}
      >
        <CanvasImage
          name="Bandeja"
          src={staticFile("fotos/perros-bandeja.jpg")}
          width={552}
          height={740}
          fit="cover"
          style={{
            scale: interpolate(frame, [6, 93], [1.18, 1.04], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              output: "perceptual-scale",
            }),
          }}
        />
      </Interactive.Div>

      <Interactive.Div
        name="Foto perro"
        style={{
          position: "absolute",
          left: 400,
          top: 1040,
          width: 630,
          height: 474,
          borderRadius: 40,
          border: `14px solid ${brand.colors.light}`,
          boxSizing: "border-box",
          overflow: "hidden",
          boxShadow: "0px 36px 60px rgba(0,0,0,0.5)",
          translate: interpolate(
            frame,
            [14, 38, 93],
            ["900px 500px", "0px 0px", "-10px -22px"],
            {
              easing: [Easing.spring({ damping: 14 }), Easing.linear],
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
          rotate: interpolate(frame, [14, 38, 93], ["30deg", "6deg", "4deg"], {
            easing: [Easing.spring({ damping: 12 }), Easing.linear],
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <CanvasImage
          name="Perro"
          src={staticFile("fotos/perro-carne.jpg")}
          width={602}
          height={446}
          fit="cover"
          style={{
            scale: interpolate(frame, [14, 93], [1.04, 1.18], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              output: "perceptual-scale",
            }),
          }}
        />
      </Interactive.Div>
      <Audio
        name="SFX transición"
        from={3}
        src={staticFile("sfx/whoosh.wav")}
        volume={0.48}
      />
      <Audio
        name="SFX título 1"
        from={9}
        src={staticFile("sfx/pop.wav")}
        volume={0.3}
      />
      <Audio
        name="SFX título 2"
        from={15}
        src={staticFile("sfx/pop.wav")}
        volume={0.36}
      />
      <Audio
        name="SFX foto 1"
        from={14}
        src={staticFile("sfx/thud.wav")}
        volume={0.45}
      />
      <Audio
        name="SFX foto 2"
        from={23}
        src={staticFile("sfx/thud.wav")}
        volume={0.45}
      />
    </AbsoluteFill>
  );
};
