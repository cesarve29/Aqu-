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

const PhoneIcon: React.FC<{ size: number; color: string }> = ({
  size,
  color,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.2.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2z" />
  </svg>
);

const CameraIcon: React.FC<{ size: number; color: string }> = ({
  size,
  color,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={2.2}
  >
    <rect x="3" y="3" width="18" height="18" rx="5.5" />
    <circle cx="12" cy="12" r="4.2" />
    <circle cx="17.3" cy="6.7" r="1.1" fill={color} stroke="none" />
  </svg>
);

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill name="Cierre">
      <Background tone="dark" centerY={430} />

      <CanvasImage
        name="Logo"
        src={staticFile("logo.png")}
        width={460}
        height={460}
        style={{
          position: "absolute",
          left: 310,
          top: 200,
          filter: "drop-shadow(0px 24px 50px rgba(0,0,0,0.6))",
          scale: interpolate(frame, [6, 30], [0, 1], {
            easing: Easing.spring({ damping: 10 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: interpolate(frame, [6, 30, 156], ["-30deg", "0deg", "4deg"], {
            easing: [Easing.spring({ damping: 11 }), Easing.linear],
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />

      <Interactive.Div
        name="Titular"
        style={{
          position: "absolute",
          left: 0,
          top: 690,
          width: 1080,
          textAlign: "center",
          fontFamily: displayFont,
          fontSize: 250,
          letterSpacing: 6,
          lineHeight: 1,
          color: brand.colors.yellow,
          textShadow: `10px 10px 0px ${brand.colors.red}`,
          scale: interpolate(frame, [16, 36], [0, 1], {
            easing: Easing.spring({ damping: 9 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          rotate: "-4deg",
        }}
      >
        ¡PIDE YA!
      </Interactive.Div>

      <Interactive.Div
        name="Etiqueta domicilios"
        style={{
          position: "absolute",
          left: 0,
          top: 990,
          width: 1080,
          textAlign: "center",
          fontFamily: bodyFont,
          fontWeight: 800,
          fontSize: 56,
          letterSpacing: 10,
          color: brand.colors.light,
          opacity: interpolate(frame, [30, 44], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          translate: interpolate(frame, [30, 46], ["0px 50px", "0px 0px"], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        DOMICILIOS
      </Interactive.Div>

      <Interactive.Div
        name="Teléfono"
        style={{
          position: "absolute",
          left: 80,
          top: 1090,
          width: 920,
          height: 210,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 28,
          borderRadius: 999,
          backgroundColor: brand.colors.yellow,
          boxShadow: `0px 14px 0px ${brand.colors.red}`,
          fontFamily: displayFont,
          fontSize: 136,
          letterSpacing: 4,
          color: brand.colors.dark,
          translate: interpolate(frame, [36, 58], ["0px 900px", "0px 0px"], {
            easing: Easing.spring({ damping: 14 }),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          scale: interpolate(
            frame,
            [70, 80, 90, 104, 114, 124],
            [1, 1.07, 1, 1, 1.07, 1],
            {
              easing: Easing.inOut(Easing.quad),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              output: "perceptual-scale",
            },
          ),
        }}
      >
        <PhoneIcon size={110} color={brand.colors.red} />
        {brand.phone}
      </Interactive.Div>

      <Interactive.Div
        name="Instagram"
        style={{
          position: "absolute",
          left: 0,
          top: 1370,
          width: 1080,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 24,
          fontFamily: bodyFont,
          fontWeight: 800,
          fontSize: 76,
          color: brand.colors.light,
          opacity: interpolate(frame, [50, 62], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          translate: interpolate(frame, [50, 68], ["0px 70px", "0px 0px"], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <CameraIcon size={96} color={brand.colors.yellow} />
        {brand.instagram}
      </Interactive.Div>
      <Audio
        name="SFX transición"
        from={3}
        src={staticFile("sfx/whoosh.wav")}
        volume={0.68}
      />
      <Audio
        name="SFX golpe logo"
        from={10}
        src={staticFile("sfx/impact.wav")}
        volume={0.7}
      />
      <Audio
        name="SFX titular"
        from={18}
        src={staticFile("sfx/pop.wav")}
        volume={0.63}
      />
      <Audio
        name="SFX teléfono sube"
        from={36}
        src={staticFile("sfx/swish.wav")}
        volume={0.43}
      />
      <Audio
        name="SFX teléfono"
        from={43}
        src={staticFile("sfx/thud.wav")}
        volume={0.82}
      />
      <Audio
        name="SFX Instagram"
        from={51}
        src={staticFile("sfx/pop.wav")}
        volume={0.43}
      />
      <Audio
        name="SFX pulso 1"
        from={72}
        src={staticFile("sfx/thud.wav")}
        volume={0.43}
      />
      <Audio
        name="SFX pulso 2"
        from={106}
        src={staticFile("sfx/thud.wav")}
        volume={0.43}
      />
    </AbsoluteFill>
  );
};
