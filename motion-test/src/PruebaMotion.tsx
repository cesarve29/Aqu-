import { TransitionSeries, springTiming } from "@remotion/transitions";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useVideoConfig } from "remotion";
import { Contador } from "./Contador";
import { Formas } from "./Formas";
import { Rotulo } from "./Rotulo";
import { Titular } from "./Titular";

// 4 escenas de 135 fotogramas menos 3 transiciones de 20 = 480 fotogramas (16 s).
export const PruebaMotion: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <TransitionSeries>
      <TransitionSeries.Sequence name="Titular" durationInFrames={135}>
        <Titular />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={wipe({ direction: "from-left" })}
        timing={springTiming({ config: { damping: 200 }, durationInFrames: 20 })}
      />
      <TransitionSeries.Sequence name="Formas" durationInFrames={135}>
        <Formas />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={clockWipe({ width, height })}
        timing={springTiming({ config: { damping: 200 }, durationInFrames: 20 })}
      />
      <TransitionSeries.Sequence name="Contador" durationInFrames={135}>
        <Contador />
      </TransitionSeries.Sequence>
      <TransitionSeries.Transition
        presentation={slide({ direction: "from-bottom" })}
        timing={springTiming({ config: { damping: 200 }, durationInFrames: 20 })}
      />
      <TransitionSeries.Sequence name="Rótulo" durationInFrames={135}>
        <Rotulo />
      </TransitionSeries.Sequence>
    </TransitionSeries>
  );
};
