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

export const Toppings: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Toppings">
      <Background tone="yellow" centerY={960} />

      <Interactive.Div
        name="Título 1"
        style={{
          position: "absolute",
          left: 0,
          top: 215,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 220,
          lineHeight: 1,
          letterSpacing: 5,
          color: brand.colors.dark,
          textShadow: `9px 9px 0px ${brand.colors.light}`,
          translate: interpolate(frame, [8, 28], ["0px -520px", "0px 0px"], {
            easing: Easing.spring({ damping: 13 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: "-3deg",
        }}
      >
        ¡ÁRMALO
      </Interactive.Div>
      <Interactive.Div
        name="Título 2"
        style={{
          position: "absolute",
          left: 0,
          top: 420,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 170,
          lineHeight: 1,
          letterSpacing: 5,
          color: brand.colors.red,
          textShadow: `8px 8px 0px ${brand.colors.dark}`,
          scale: interpolate(frame, [23, 41], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: "-3deg",
        }}
      >
        A TU GUSTO!
      </Interactive.Div>

      <Interactive.Div
        name="Marco barra"
        style={{
          position: "absolute",
          left: 50,
          top: 650,
          width: 980,
          height: 700,
          borderRadius: 44,
          border: `14px solid ${brand.colors.dark}`,
          boxSizing: "border-box",
          overflow: "hidden",
          boxShadow: `16px 18px 0px ${brand.colors.red}`,
          translate: interpolate(frame, [4, 28], ["0px 1400px", "0px 0px"], {
            easing: Easing.spring({ damping: 14 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          rotate: interpolate(frame, [4, 28], ["10deg", "2deg"], {
            easing: Easing.spring({ damping: 12 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <CanvasImage
          name="Barra de toppings"
          src={staticFile("fotos/toppings.jpg")}
          width={1264}
          height={720}
          fit="cover"
          style={{
            position: "absolute",
            left: 0,
            top: -24,
            maxWidth: "none",
            translate: interpolate(frame, [10, 93], ["0px 0px", "-312px 0px"], {
              easing: Easing.inOut(Easing.quad),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        />
      </Interactive.Div>

      <Interactive.Div
        name="Lista 1"
        style={{
          position: "absolute",
          left: 0,
          top: 1410,
          whiteSpace: "nowrap",
          fontFamily: displayFont,
          fontSize: 86,
          lineHeight: 1,
          letterSpacing: 3,
          color: brand.colors.dark,
          translate: interpolate(frame, [0, 93], ["1080px 0px", "-760px 0px"], {
            easing: Easing.out(Easing.quad),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        QUESO ★ MAÍZ ★ PAPA CHIP ★ NACHOS ★ PIÑA ★ CEBOLLA
      </Interactive.Div>
      <Interactive.Div
        name="Lista 2"
        style={{
          position: "absolute",
          left: 0,
          top: 1508,
          whiteSpace: "nowrap",
          fontFamily: displayFont,
          fontSize: 86,
          lineHeight: 1,
          letterSpacing: 3,
          color: brand.colors.red,
          translate: interpolate(
            frame,
            [0, 93],
            ["-1700px 0px", "-120px 0px"],
            {
              easing: Easing.out(Easing.quad),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
        }}
      >
        PICO DE GALLO ★ MADURO ★ JALAPEÑOS ★ PEPINOS ★ PICO DE GALLO
      </Interactive.Div>
      <Audio
        name="SFX transición"
        from={3}
        src={staticFile("sfx/whoosh.wav")}
        volume={0.48}
      />
      <Audio
        name="SFX marco"
        from={12}
        src={staticFile("sfx/thud.wav")}
        volume={0.51}
      />
      <Audio
        name="SFX título 1"
        from={14}
        src={staticFile("sfx/swish.wav")}
        volume={0.24}
      />
      <Audio
        name="SFX título 2"
        from={24}
        src={staticFile("sfx/pop.wav")}
        volume={0.36}
      />
    </AbsoluteFill>
  );
};
