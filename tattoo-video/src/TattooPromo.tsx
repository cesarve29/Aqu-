import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { CarouselScene } from "./CarouselScene";
import { IntroScene } from "./IntroScene";
import { OutroScene } from "./OutroScene";
import { ProcessScene } from "./ProcessScene";
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
    <TransitionSeries.Sequence name="Carousel" durationInFrames={212}>
      <CarouselScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Showcase" durationInFrames={300}>
      <ShowcaseScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Process" durationInFrames={150}>
      <ProcessScene />
    </TransitionSeries.Sequence>
    <TransitionSeries.Transition
      presentation={fade()}
      timing={linearTiming({ durationInFrames: 12 })}
    />
    <TransitionSeries.Sequence name="Outro" durationInFrames={170}>
      <OutroScene />
    </TransitionSeries.Sequence>
  </TransitionSeries>
);
