import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { blurSlide } from "@remotion/transitions/blur-slide";
import { Easing } from "remotion";
import { BurgerVideo } from "./scenes/BurgerVideo";
import { HotDogPhotos } from "./scenes/HotDogPhotos";
import { HotDogVideo } from "./scenes/HotDogVideo";
import { Intro } from "./scenes/Intro";
import { Outro } from "./scenes/Outro";
import { Toppings } from "./scenes/Toppings";

// Barrido con desenfoque de movimiento: une las escenas sin cortes secos.
const whip = () =>
  linearTiming({
    durationInFrames: 18,
    easing: Easing.bezier(0.76, 0, 0.24, 1),
  });

export const Ad: React.FC = () => {
  return (
    <TransitionSeries>
      <TransitionSeries.Sequence name="Intro" durationInFrames={100}>
        <Intro />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={blurSlide({ direction: "from-right" })}
        timing={whip()}
      />
      <TransitionSeries.Sequence name="Perros video" durationInFrames={110}>
        <HotDogVideo />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={blurSlide({ direction: "from-bottom" })}
        timing={whip()}
      />
      <TransitionSeries.Sequence name="Perros fotos" durationInFrames={90}>
        <HotDogPhotos />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={blurSlide({ direction: "from-right" })}
        timing={whip()}
      />
      <TransitionSeries.Sequence name="Toppings" durationInFrames={100}>
        <Toppings />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={blurSlide({ direction: "from-bottom" })}
        timing={whip()}
      />
      <TransitionSeries.Sequence name="Hamburguesa" durationInFrames={110}>
        <BurgerVideo />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={blurSlide({ direction: "from-right" })}
        timing={whip()}
      />
      <TransitionSeries.Sequence name="Cierre" durationInFrames={156}>
        <Outro />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
