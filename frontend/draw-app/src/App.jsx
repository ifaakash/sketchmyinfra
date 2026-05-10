import React from "react";
import { Excalidraw } from "@excalidraw/excalidraw";

export default function App() {
  return (
    <Excalidraw
      theme="light"
      UIOptions={{
        canvasActions: {
          loadScene: false,
          saveToActiveFile: false,
        },
      }}
    />
  );
}
