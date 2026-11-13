import { Composition, Folder } from "remotion";
import { CarouselScene } from "./CarouselScene";
import { IntroScene } from "./IntroScene";
import { OutroScene } from "./OutroScene";
import { ShowcaseScene } from "./ShowcaseScene";
import { TattooPromo } from "./TattooPromo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="TattooPromo-Scenes">
        <Composition id="Intro" component={IntroScene} width={1080} height={1920} fps={30} durationInFrames={120} />
        <Composition id="Carousel" component={CarouselScene} width={1080} height={1920} fps={30} durationInFrames={192} />
        <Composition id="Showcase" component={ShowcaseScene} width={1080} height={1920} fps={30} durationInFrames={250} />
        <Composition id="Outro" component={OutroScene} width={1080} height={1920} fps={30} durationInFrames={136} />
      </Folder>
      <Composition
        id="TattooPromo"
        component={TattooPromo}
        width={1080}
        height={1920}
        fps={30}
        durationInFrames={662}
      />
    </>
  );
};
