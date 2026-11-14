import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { blurSlide } from "@remotion/transitions/blur-slide";
import { Audio } from "@remotion/media";
import { Easing, staticFile } from "remotion";
import { BurgerVideo } from "./scenes/BurgerVideo";
import { HotDogPhotos } from "./scenes/HotDogPhotos";
import { HotDogVideo } from "./scenes/HotDogVideo";
import { Intro } from "./scenes/Intro";
import { Outro } from "./scenes/Outro";
import { Toppings } from "./scenes/Toppings";

// La música va a 120 BPM (un pulso cada 15 fotogramas). Las duraciones de las
// escenas hacen que el centro de cada transición caiga sobre un pulso.

// Barrido con desenfoque de movimiento: une las escenas sin cortes secos.
const whip = () =>
  linearTiming({
    durationInFrames: 18,
    easing: Easing.bezier(0.76, 0, 0.24, 1),
  });

export const Ad: React.FC = () => {
  return (
    <>
      <Audio name="Música" src={staticFile("music/fondo.mp3")} volume={0.6} />
      <TransitionSeries>
        <TransitionSeries.Sequence name="Intro" durationInFrames={99}>
          <Intro />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={blurSlide({ direction: "from-right" })}
          timing={whip()}
        />
        <TransitionSeries.Sequence name="Perros video" durationInFrames={108}>
          <HotDogVideo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={blurSlide({ direction: "from-bottom" })}
          timing={whip()}
        />
        <TransitionSeries.Sequence name="Perros fotos" durationInFrames={93}>
          <HotDogPhotos />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={blurSlide({ direction: "from-right" })}
          timing={whip()}
        />
        <TransitionSeries.Sequence name="Toppings" durationInFrames={93}>
          <Toppings />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={blurSlide({ direction: "from-bottom" })}
          timing={whip()}
        />
        <TransitionSeries.Sequence name="Hamburguesa" durationInFrames={108}>
          <BurgerVideo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={blurSlide({ direction: "from-right" })}
          timing={whip()}
        />
        <TransitionSeries.Sequence name="Cierre" durationInFrames={165}>
          <Outro />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </>
  );
};
