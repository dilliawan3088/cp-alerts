import { defineConfig } from "@trigger.dev/sdk/v3";
import { aptGet, additionalFiles } from "@trigger.dev/build/extensions/core";


export default defineConfig({
  project: "proj_goemmgnyudhmomjfmrsb",
  runtime: "node",
  logLevel: "info",
  retries: {
    enabledInDev: true,
    default: {
      maxAttempts: 3,
      minTimeoutInMs: 1000,
      maxTimeoutInMs: 10000,
      factor: 2,
      randomize: true,
    },
  },
  maxDuration: 3600, // 1 hour global limit for backlog processing


  build: {
    extensions: [
      // 1. Install Python and venv
      aptGet({
        packages: ["python3", "python3-pip", "python3-venv"],
      }),
      // 2. Clear instructions to include your files
      additionalFiles({
        files: [
          "main.py",
          "requirements.txt",
          "checks/**/*.py",
          "notifications/**/*.py",
          "tools/**/*.py",
          "credentials/**/*.json",
        ],
      }),
      // 3. Create a virtual environment and install dependencies
      {
        name: "python-venv",
        onBuildStart: (context: any) => {
          context.addLayer({
            id: "python-venv",
            commands: [
              "python3 -m venv .venv",
              "./.venv/bin/pip install --no-cache-dir -r requirements.txt",
            ],
          });
        },
      },


    ],
  },
});