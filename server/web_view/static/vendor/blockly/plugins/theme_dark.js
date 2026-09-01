/**
 * @license
 * Vendored from RaspberryPiFoundation/blockly: @blockly/theme-dark v13.1.0
 * (source commit 1aa51c0ec48f73ca1214397fa70d141ac47a57fe,
 * packages/plugins/theme-dark/src/index.ts).
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 *
 * The plugin's entire source is one Blockly.Theme.defineTheme call; this is a
 * plain-JS port of that file (the npm UMD build would expose the theme via
 * the unusable `window.default`), exposing it as Blockly.Themes.Dark.
 */
Blockly.Themes.Dark = Blockly.Theme.defineTheme('dark', {
    name: 'dark',
    base: Blockly.Themes.Classic,
    componentStyles: {
        workspaceBackgroundColour: '#1e1e1e',
        toolboxBackgroundColour: '#333',
        toolboxForegroundColour: '#fff',
        flyoutBackgroundColour: '#252526',
        flyoutForegroundColour: '#ccc',
        flyoutOpacity: 1,
        scrollbarColour: '#797979',
        insertionMarkerColour: '#fff',
        insertionMarkerOpacity: 0.3,
        scrollbarOpacity: 0.4,
        cursorColour: '#d0d0d0',
    },
});