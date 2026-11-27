/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs.
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import fs from "node:fs";
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);

// Cloud container: Remotion can't download its own Chrome here, so reuse the
// pre-installed headless shell when present. No effect on other machines.
const localHeadlessShell = "/opt/pw-browsers/chromium_headless_shell";
if (fs.existsSync(localHeadlessShell)) {
  Config.setBrowserExecutable(localHeadlessShell);
}
