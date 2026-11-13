import { Composition, Folder } from "remotion";
import { Contador } from "./Contador";
import { Formas } from "./Formas";
import { PruebaMotion } from "./PruebaMotion";
import { Rotulo } from "./Rotulo";
import { Titular } from "./Titular";

const scene = { width: 1920, height: 1080, fps: 30, durationInFrames: 135 };

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="PruebaMotion-Escenas">
        <Composition id="Titular" component={Titular} {...scene} />
        <Composition id="Formas" component={Formas} {...scene} />
        <Composition id="Contador" component={Contador} {...scene} />
        <Composition id="Rotulo" component={Rotulo} {...scene} />
      </Folder>
      <Composition
        id="PruebaMotion"
        component={PruebaMotion}
        width={1920}
        height={1080}
        fps={30}
        durationInFrames={480}
      />
    </>
  );
};
