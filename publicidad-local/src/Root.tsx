import { Composition, Folder } from "remotion";
import { Ad } from "./Ad";
import { BurgerVideo } from "./scenes/BurgerVideo";
import { HotDogPhotos } from "./scenes/HotDogPhotos";
import { HotDogVideo } from "./scenes/HotDogVideo";
import { Intro } from "./scenes/Intro";
import { Outro } from "./scenes/Outro";
import { Toppings } from "./scenes/Toppings";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Escenas">
        <Composition
          id="Intro"
          component={Intro}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={100}
        />
        <Composition
          id="PerrosVideo"
          component={HotDogVideo}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={110}
        />
        <Composition
          id="PerrosFotos"
          component={HotDogPhotos}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={90}
        />
        <Composition
          id="Toppings"
          component={Toppings}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={100}
        />
        <Composition
          id="Hamburguesa"
          component={BurgerVideo}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={110}
        />
        <Composition
          id="Cierre"
          component={Outro}
          width={1080}
          height={1920}
          fps={30}
          durationInFrames={156}
        />
      </Folder>
      <Composition
        id="PerroLoco"
        component={Ad}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={576}
      />
    </>
  );
};
