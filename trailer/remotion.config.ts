import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(2);
// Headless Linux rendering without a GPU — software ANGLE backend.
Config.setChromiumOpenGlRenderer("angle");
