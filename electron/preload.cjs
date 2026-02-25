const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("sailorDesktop", {
  platform: process.platform,
  isDesktop: true,
});
