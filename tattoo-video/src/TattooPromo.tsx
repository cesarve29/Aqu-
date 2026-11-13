import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { CarouselScene } from "./CarouselScene";
import { IntroScene } from "./IntroScene";
import { OutroScene } from "./OutroScene";
import { ShowcaseScene } from "./ShowcaseScene";

export const TattooPromo: React.FC = () => (
  <TransitionSeries>
    <TransitionSeries.Sequence name="Intro" durationInFrames={120}>
      <IntroScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Carousel" durationInFrames={192}>
      <CarouselScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Showcase" durationInFrames={250}>
      <ShowcaseScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Outro" durationInFrames={136}>
      <OutroScene />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);
